"""
JOYST CORPORATION AUTH - Master Plan Upgrade Key Generator CLI
Used by the Platform Owner/Admin to generate valid Paid Plan Keys.
"""

import sys
import os
import argparse

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal, PlanKey
from server.security import generate_random_token

def generate_keys(target_plan: str = "Paid", count: int = 1):
    target_plan = "Paid"
    count = max(1, count)

    db = SessionLocal()
    generated = []

    try:
        for _ in range(count):
            token = generate_random_token(12).upper()
            # Format: JOYST-PAID-XXXX-XXXX-XXXX
            key_code = f"JOYST-PAID-{token[:4]}-{token[4:8]}-{token[8:12]}"

            new_key = PlanKey(
                key_code=key_code,
                target_plan=target_plan,
                is_used=False
            )
            db.add(new_key)
            generated.append(key_code)

        db.commit()

        print("\n=======================================================")
        print(f"[+] Successfully Generated {len(generated)} {target_plan} Upgrade Keys:")
        print("=======================================================")
        for k in generated:
            print(f"[KEY] {k}")
        print("=======================================================\n")

    except Exception as e:
        db.rollback()
        print(f"\n[-] Error generating keys: {e}\n")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Joyst Corp Auth Paid Upgrade Keys")
    parser.add_argument("--plan", type=str, default="Paid", help="Plan name (Paid)")
    parser.add_argument("--count", type=int, default=1, help="Number of keys to generate")

    args = parser.parse_args()
    generate_keys(args.plan, args.count)
