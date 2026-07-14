class SessionNotFoundError(Exception):
    def __init__(self, session_id: object) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")
