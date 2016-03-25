class CannotOverwriteExistingCassetteException(Exception):
    def __init__(self, request, fixture, mode):
        self.request = request
        self.fixture = fixture
        self.mode = mode
        super(CannotOverwriteExistingCassetteException, self).__init__(
            "No match for %r was found in the vcrpy cassette %r."
            "Can't overwrite the cassette in record mode %r."
            % (self.request, self.fixture, self.mode))


class UnhandledHTTPRequestError(Exception):
    """Raised when a cassette does not contain the request we want."""
    pass
