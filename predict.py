"""Transparent PHQ-9 scoring used when no clinically validated ML dataset is available."""


def score_phq9(answers):
    if len(answers) != 9 or any(value not in range(4) for value in answers):
        raise ValueError("PHQ-9 requires nine values from 0 through 3")
    return sum(answers)
