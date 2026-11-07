import unittest
from unittest.mock import MagicMock

from app import Handler


class HandlerTests(unittest.TestCase):
    def test_disconnected_client_does_not_raise_while_sending_response(self):
        for error in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            with self.subTest(error=error.__name__):
                handler = Handler.__new__(Handler)
                handler.send_response = MagicMock()
                handler.send_header = MagicMock()
                handler.end_headers = MagicMock()
                handler.wfile = MagicMock()
                handler.wfile.write.side_effect = error()

                handler.send(200, b'{"ok": true}')
