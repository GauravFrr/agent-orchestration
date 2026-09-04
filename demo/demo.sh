#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "          Agent Orchestration System — Automated Demo Walkthrough      "
echo "======================================================================"

API_URL=${API_BASE_URL:-"http://localhost:8000"}

echo ""
echo "1. Checking System Health & API Availability at $API_URL..."
curl -s "$API_URL/tasks" > /dev/null || { echo "API service is not reachable at $API_URL"; exit 1; }
echo "   API Service is LIVE and healthy."

echo ""
echo "2. Running Scripted End-to-End Narrative Scenario..."
python demo/demo_scenario.py

echo ""
echo "======================================================================"
echo "          Demo Walkthrough Completed Successfully!                     "
echo "======================================================================"
