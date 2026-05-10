NO         = 0  # the guess is factually wrong
YES        = 1  # the guess is factually correct
INDECISIVE = 2  # the host cannot give a clear yes/no (e.g. "sometimes")
REFUSAL    = 3  # the host refuses to answer this question
WIN        = 4  # the guesser correctly identified the challenge subject

VALID_CODES = {NO, YES, INDECISIVE, REFUSAL, WIN}
