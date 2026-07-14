class SessionNotFoundError(Exception):
    def __init__(self, session_id: object) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: object) -> None:
        self.document_id = document_id
        super().__init__(f"Document {document_id} not found")
