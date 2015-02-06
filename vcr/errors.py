class CannotOverwriteExistingCassetteException(Exception):
    pass


class UnhandledHTTPRequestError(Exception):
    '''
    Raised when a cassette does not c
    ontain the request we want
    '''
    pass
