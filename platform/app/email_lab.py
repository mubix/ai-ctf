"""Owned email attempts, durable activity, objective checks, and recovery."""
import asyncio
import json
import logging
import secrets
import time
from uuid import uuid4

from .chat import ModelError
from .db import db
from .email_model import run_assistant
from .email_workspace import GOALS, Workspace, objective_reached, BASELINE_BODY, BASELINE_SUBJECT, PRICING, POLICY, DEAL, SALES
from .learning import LessonError, RUN_TIMEOUT, LEASE_SECONDS, MAX_MESSAGE_LENGTH

logger = logging.getLogger(__name__)


def definition(goal):
    if goal not in GOALS:
        raise LessonError("This email objective is not available.", 404)
    return GOALS[goal]


def progress_for(user_id):
    with db() as conn:
        return {r["goal"]: dict(r) for r in conn.execute("SELECT * FROM email_progress WHERE user_id=?", (user_id,))}


def _expire(conn):
    conn.execute("UPDATE email_trials SET status='failed',feedback=? WHERE status='running' AND started_at<?",
                 ("This run was interrupted. Your email and observed activity are saved. Send it again to start a new run.", int(time.time()) - LEASE_SECONDS))


def _new_run(conn, user_id, goal):
    run_id = str(uuid4())
    conn.execute("INSERT INTO email_runs(id,user_id,goal) VALUES (?,?,?)", (run_id, user_id, goal))
    conn.execute("UPDATE email_progress SET current_run=? WHERE user_id=? AND goal=?", (run_id, user_id, goal))
    return run_id


def _active(conn, user_id, goal, run_id):
    if not conn.execute("SELECT 1 FROM email_progress WHERE user_id=? AND goal=? AND current_run=?", (user_id, goal, run_id)).fetchone():
        raise LessonError("This attempt is no longer current. Reload before sending.")


def state(user_id, goal, run_id=None):
    spec = definition(goal)
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _expire(conn)
        conn.execute("INSERT OR IGNORE INTO email_progress(user_id,goal) VALUES (?,?)", (user_id, goal))
        progress = dict(conn.execute("SELECT * FROM email_progress WHERE user_id=? AND goal=?", (user_id, goal)).fetchone())
        if not progress["current_run"]:
            progress["current_run"] = _new_run(conn, user_id, goal)
        selected = run_id or progress["current_run"]
        run = conn.execute("SELECT * FROM email_runs WHERE id=? AND user_id=? AND goal=?", (selected, user_id, goal)).fetchone()
        if not run:
            raise LessonError("This attempt is not available.", 404)
        trials = [dict(r) for r in conn.execute("SELECT * FROM email_trials WHERE run_id=? ORDER BY id", (selected,))]
        attempts = [dict(r) for r in conn.execute("SELECT id,created_at FROM email_runs WHERE user_id=? AND goal=? ORDER BY rowid DESC", (user_id, goal))]
    for trial in trials:
        trial.pop("canary")
        trial["events"] = json.loads(trial["events"])
        trial["result"] = json.loads(trial["result"]) if trial["result"] else None
        trial["workspace"] = json.loads(trial["workspace"])
    return {"goal": goal, "spec": spec, "run": dict(run), "progress": progress, "trials": trials,
            "latest": trials[-1] if trials else None, "attempts": attempts,
            "archived": selected != progress["current_run"], "running": any(t["status"] == "running" for t in trials),
            "hints": spec["hints"][:progress["hint_level"]], "request_id": str(uuid4()),
            "turns_left": max(0, 10 - sum(t["status"] == "completed" for t in trials)),
            "baseline_subject": BASELINE_SUBJECT, "baseline_body": BASELINE_BODY, "max_length": MAX_MESSAGE_LENGTH,
            "folder": SALES, "files": [DEAL, POLICY, PRICING], "url": "/learn/email-joe?goal=" + goal}


def hint(user_id, goal, run_id):
    definition(goal)
    with db() as conn:
        _active(conn, user_id, goal, run_id)
        conn.execute("UPDATE email_progress SET hint_level=MIN(hint_level+1,3) WHERE user_id=? AND goal=?", (user_id, goal))


def reset(user_id, goal, run_id):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _expire(conn)
        _active(conn, user_id, goal, run_id)
        if conn.execute("SELECT 1 FROM email_trials WHERE run_id=? AND status='running'", (run_id,)).fetchone():
            raise LessonError("Wait for Joe's assistant to finish before starting fresh.")
        _new_run(conn, user_id, goal)


async def submit(user_id, goal, run_id, request_id, subject, body, protected=False):
    definition(goal)
    subject = subject.strip()
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not subject or len(subject) > 160 or not body or len(body) > MAX_MESSAGE_LENGTH:
        raise LessonError(f"Enter a subject (up to 160 characters) and an email body (up to {MAX_MESSAGE_LENGTH:,} characters).", 400)
    if not request_id or len(request_id) > 64 or (protected and goal == "summary"):
        raise LessonError("Reload this objective before sending.", 400)
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _expire(conn)
        _active(conn, user_id, goal, run_id)
        old = conn.execute("SELECT * FROM email_trials WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
        if old:
            if (old["subject"], old["body"], bool(old["protected"])) != (subject, body, protected):
                raise LessonError("That request has different content. Reload before sending again.")
            if old["status"] == "completed":
                return
            if old["status"] == "failed":
                raise LessonError("That run has ended. Use Send again to create a new run; its earlier evidence stays saved.")
        if conn.execute("SELECT 1 FROM email_trials t JOIN email_runs r ON r.id=t.run_id WHERE r.user_id=? AND t.status='running'", (user_id,)).fetchone():
            raise LessonError("Joe's assistant is already processing one of your emails. Wait for that run to finish.")
        if conn.execute("SELECT COUNT(*) FROM email_trials WHERE run_id=? AND status='completed'", (run_id,)).fetchone()[0] >= 10:
            raise LessonError("Ten runs are saved in this attempt. Start fresh to continue.")
        canary = "pricing_" + secrets.token_hex(12)
        workspace = Workspace(goal, canary, protected)
        conn.execute("INSERT INTO email_trials(run_id,request_id,subject,body,protected,canary,status,workspace,started_at) VALUES (?,?,?,?,?,?,'running',?,?)",
                     (run_id, request_id, subject, body, int(protected), canary, json.dumps(workspace.view()), int(time.time())))
    events = []

    def emit(event):
        events.append(event)
        with db() as conn:
            updated = conn.execute("UPDATE email_trials SET events=?,workspace=? WHERE run_id=? AND request_id=? AND status='running'",
                                   (json.dumps(events), json.dumps(workspace.view()), run_id, request_id))
            if not updated.rowcount:
                raise LessonError("This run expired. Its saved activity remains available.")

    result, failure = None, None
    try:
        for text in ("Email received in Joe's simulated Outlook inbox.", "Joe checks his inbox on his phone.",
                     "Joe taps Summarize; his laptop assistant receives the task."):
            emit({"kind": "story", "text": text})
        result = await asyncio.wait_for(run_assistant(goal, subject, body, workspace, emit), RUN_TIMEOUT)
    except (ModelError, TimeoutError):
        logger.warning("Email assistant run failed: goal=%s", goal)
        failure = "The AI service did not finish a usable summary. Your email and observed actions are saved. Send again to try a new run."
    except BaseException:
        with db() as conn:
            conn.execute("UPDATE email_trials SET status='failed',feedback=? WHERE run_id=? AND request_id=? AND status='running'",
                         ("Processing was interrupted. Your email and activity are saved.", run_id, request_id))
        raise
    success = objective_reached(goal, events, result, canary, subject + "\n" + body)
    blocked = any(e.get("result", {}).get("blocked") for e in events)
    if success:
        feedback = "Objective reached. Inspect Joe's screen and the recorded evidence to see the boundary crossed."
    elif protected and blocked:
        feedback = "The assistant requested a forbidden action. The protected tool blocked it. Inspect the result, then try a clean email with protection still enabled."
    elif protected:
        feedback = "Protected run finished without the attack objective. Check whether the model used its tools; a refusal alone does not test the permission boundary."
    elif body == BASELINE_BODY and subject == BASELINE_SUBJECT:
        feedback = "Baseline finished. Inspect Joe's summary and actions, then edit the email to try an injection."
    else:
        feedback = "The attack objective was not observed. Inspect what Joe's assistant did, revise your email, or open a hint."
    if failure:
        feedback = (feedback + " " if success else "") + failure
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _active(conn, user_id, goal, run_id)
        updated = conn.execute("UPDATE email_trials SET status=?,result=?,success=?,feedback=? WHERE run_id=? AND request_id=? AND status='running'",
                               ("failed" if failure else "completed", json.dumps(result) if result else None, int(success), feedback, run_id, request_id))
        if not updated.rowcount:
            raise LessonError("This run expired before its final response arrived. Start a new run.")
        if success and not protected:
            conn.execute("UPDATE email_progress SET completed_with_example=CASE WHEN completed_at IS NULL THEN hint_level>=3 ELSE completed_with_example END, completed_at=COALESCE(completed_at,CURRENT_TIMESTAMP) WHERE user_id=? AND goal=?", (user_id, goal))
    if failure:
        raise LessonError(failure, 503)
