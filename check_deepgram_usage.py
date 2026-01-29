#!/usr/bin/env python3
"""
Check Deepgram API usage and remaining credits.

Usage:
    python check_deepgram_usage.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()


def check_usage():
    api_key = os.getenv("DEEPGRAM_API_KEY")

    if not api_key:
        print("Error: DEEPGRAM_API_KEY not found in .env")
        return

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    # Get projects
    print("Deepgram Usage Report")
    print("=" * 60)

    try:
        # Get project info
        resp = requests.get(
            "https://api.deepgram.com/v1/projects",
            headers=headers
        )
        resp.raise_for_status()
        projects = resp.json()

        for project in projects.get("projects", []):
            project_id = project["project_id"]
            project_name = project.get("name", "Unnamed")

            print(f"\nProject: {project_name}")
            print(f"ID: {project_id}")
            print("-" * 40)

            # Get balances
            balance_resp = requests.get(
                f"https://api.deepgram.com/v1/projects/{project_id}/balances",
                headers=headers
            )

            if balance_resp.status_code == 200:
                balances = balance_resp.json()
                for balance in balances.get("balances", []):
                    amount = balance.get("amount", 0)
                    units = balance.get("units", "unknown")
                    balance_id = balance.get("balance_id", "")

                    print(f"  Balance: {amount:.2f} {units}")

            # Get usage summary
            usage_resp = requests.get(
                f"https://api.deepgram.com/v1/projects/{project_id}/usage",
                headers=headers,
                params={"start": "2024-01-01", "end": "2030-12-31"}
            )

            if usage_resp.status_code == 200:
                usage = usage_resp.json()
                results = usage.get("results", [])

                total_hours = 0
                total_requests = 0

                for result in results:
                    hours = result.get("hours", 0)
                    requests_count = result.get("requests", 0)
                    total_hours += hours
                    total_requests += requests_count

                print(f"  Total Hours Used: {total_hours:.2f}")
                print(f"  Total Requests: {total_requests}")
                print(f"  Total Minutes: {total_hours * 60:.1f}")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Dashboard: https://console.deepgram.com/")


if __name__ == "__main__":
    check_usage()
