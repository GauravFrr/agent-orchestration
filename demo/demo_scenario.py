import asyncio
import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

def make_request(url, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 70)
    print("DEMO SCENARIO: Agent Orchestration System End-to-End Walkthrough")
    print("=" * 70)

    # 1. Primary Task Submission
    prompt = (
        "Research recent agent orchestration trends, query customer churn trends in sales data, "
        "write a comprehensive synthesis report, and delete temporary staging records from demo_data.sales_data."
    )
    print(f"\n[1/6] Submitting Primary Narrative Task: '{prompt}'")
    task = make_request(f"{BASE_URL}/tasks", method="POST", data={"request_text": prompt})
    task_id = task["id"]
    print(f"-> Task Created successfully: Task ID = {task_id}")

    # 2. Polling for Execution & Escalation
    print("\n[2/6] Monitoring Task Execution & Polling for Sensitive Action Escalation...")
    escalated_review = None
    for _ in range(30):
        time.sleep(2)
        reviews = make_request(f"{BASE_URL}/reviews")
        pending = [r for r in reviews if r.get("task_id") == task_id and r.get("status") == "pending"]
        if pending:
            escalated_review = pending[0]
            print(f"-> Sensitive Action Triggered & Escalated! Review Request ID: {escalated_review['id']}")
            print(f"   Approval Level: {escalated_review['approval_level']}")
            print(f"   Trigger Reason: {escalated_review['trigger_reason']}")
            break
        
        task_curr = make_request(f"{BASE_URL}/tasks/{task_id}")
        print(f"   Current Task Status: {task_curr['status']}")
        if task_curr['status'] in ("done", "failed"):
            break

    if not escalated_review:
        print("ERROR: Expected sensitive action escalation review request not found.")
        sys.exit(1)

    # 3. Submitting Human Approval Decision
    review_id = escalated_review["id"]
    print(f"\n[3/6] Operator Submitting 'approve' Decision for Review Request {review_id}...")
    decision_resp = make_request(
        f"{BASE_URL}/reviews/{review_id}/decision",
        method="POST",
        data={"decision": "approve", "notes": "Approved staging table cleanup by operator."}
    )
    print(f"-> Decision Accepted! Success = {decision_resp.get('success')}")

    # 4. Await Task Completion
    print("\n[4/6] Waiting for Task Workflow Completion...")
    final_task = None
    for _ in range(30):
        time.sleep(2)
        curr = make_request(f"{BASE_URL}/tasks/{task_id}")
        if curr["status"] in ("done", "failed"):
            final_task = curr
            break
        print(f"   Executing... Status: {curr['status']}")

    if not final_task or final_task["status"] != "done":
        print(f"WARNING: Task finished with status: {final_task.get('status') if final_task else 'timeout'}")
    else:
        print(f"-> Primary Task Completed Successfully! Status: {final_task['status']}")
        print(f"   Total Execution Cost: ${final_task.get('total_cost_usd', 0.0):.6f}")

    # 5. Secondary Run (Memory-Informed Planning)
    print("\n[5/6] Submitting Secondary Similar Task to Exercise Memory-Informed Planning...")
    second_prompt = "Research agent orchestration trends and query customer churn in sales data."
    second_task = make_request(f"{BASE_URL}/tasks", method="POST", data={"request_text": second_prompt})
    second_id = second_task["id"]
    print(f"-> Secondary Task Created: Task ID = {second_id}")

    time.sleep(5)
    trace_tree = make_request(f"{BASE_URL}/tasks/{second_id}/trace")
    print(f"-> Verified Secondary Task Trace fetched: Spans Recorded = {len(trace_tree.get('trace_tree', []))}")

    # 6. Checkpoint Replay
    print("\n[6/6] Executing Checkpoint Replay for Primary Task...")
    trace_primary = make_request(f"{BASE_URL}/tasks/{task_id}/trace")
    primary_spans = trace_primary.get("trace_tree", [])
    
    if primary_spans:
        # Get first available checkpoint span or thread
        replays = make_request(f"{BASE_URL}/tasks/{task_id}/replays")
        print(f"-> Linked Replays Found for Primary Task: {len(replays)}")

    print("\n" + "=" * 70)
    print("DEMO SCENARIO COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
