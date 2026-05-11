NO           = 0  # the guess is factually wrong
YES          = 1  # the guess is factually correct
INDECISIVE   = 2  # the host cannot give a clear yes/no (e.g. "sometimes")
REFUSAL      = 3  # the host refuses to answer this question
WIN          = 4  # the guesser correctly identified the challenge subject
POSSIBLE     = 5  # the guess is possibly correct but not confirmed
POSSIBLY_NOT = 6  # the guess is probably wrong but not confirmed

VALID_CODES = {NO, YES, INDECISIVE, REFUSAL, WIN, POSSIBLE, POSSIBLY_NOT}
