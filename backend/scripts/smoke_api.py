"""Manual smoke check against a running backend: python scripts/smoke_api.py [base_url]"""
import sys, time
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CASES = [("es", "aves, arquitectura"), ("en", "birds, architecture")]

def main():
    with httpx.Client(base_url=BASE, timeout=180) as client:
        print("health:", client.get("/health").json())
        for lang, interests in CASES:
            started = time.monotonic()
            body = client.post("/missions/generate", json={"minutes": 10, "language": lang, "interests": interests}).json()
            print(f"[{lang}] source={body['source']} fallback_reason={body['fallback_reason']} {time.monotonic() - started:.0f}s")
            for m in body["missions"]:
                print(f"  - {m['title']}: {m['description']}")

if __name__ == "__main__":
    main()
