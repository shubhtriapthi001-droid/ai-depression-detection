"""Training placeholder intentionally kept explicit: do not train on invented clinical data.

A validated, consented dataset and an ethics-reviewed evaluation plan are required before
adding a predictive model. The production app therefore uses transparent PHQ-9 scoring.
"""

if __name__ == "__main__":
    print("No model trained: supply a validated dataset and evaluation plan first.")
