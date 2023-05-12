from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import logging

import urllib.parse


class RequestDispatcher(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self._middlewares = [
            ServerHeader(),
            Index(),
            NotFound(),
        ]
        self._catchall = GenericError()
        super().__init__(request, client_address, server)

    def do_GET(self):
        # resp_text = f"""<h1>Hello World!</h1>
        #     <p>Client address: {self.client_address}</p>
        #     <p>Command: {self.command}</p>
        #     <p>Path: {self.path}</p>
        #     <p>Headers: {self.headers}</p>
        # """

        # resp_data = resp_text.encode("utf8")
        # self.send_response(200)
        # self.send_header("Content-Type", "text/html; charset=utf-8")
        # self.send_header("Content-Length", len(resp_data))
        # self.end_headers()
        # self.wfile.write(resp_data)

        ctx = HttpContext(self)

        try:
            for middleware in self._middlewares:
                if middleware.handle(ctx):
                    break
        except Exception as e:
            ctx.error = e
            self._catchall.handle(ctx)
        finally:
            ctx.response.send()


class Request:
    """Provide interface to visit HTTP request information"""

    def __init__(self, handler: BaseHTTPRequestHandler):
        self._handler = handler

    @property
    def path(self) -> str:
        path, _ = urllib.parse.splitquery(self._handler.path)
        return path

    def query_string(self, key: str, default: str = None) -> str:
        _, qs = urllib.parse.splitquery(self._handler.path)
        args = dict(urllib.parse.parse_qsl(qs))
        return args.get(key, default)


class Response:
    """Provide interface to write HTTP response

    Some method return self in order to implement chain invoke.
    """

    def __init__(self, handler: BaseHTTPRequestHandler):
        self._handler = handler
        self._status = 200
        self._headers = {}
        self._data = BytesIO()

    def header(self, key: str, value: str):
        self._headers[key] = value
        return self

    def status(self, code: int):
        self._status = code
        return self

    def data(self, content: bytes):
        self._data.write(content)
        return self

    def html(self, text: str):
        self.data(text.encode("utf-8"))
        self._headers.setdefault("Content-Type", "text/html; charset=utf-8")
        return self

    def send(self):
        self._handler.send_response(self._status)
        resp_data = self._data.getvalue()
        self._headers.setdefault("Content-Length", len(resp_data))
        for k, v in self._headers.items():
            self._handler.send_header(k, v)
        self._handler.end_headers()
        self._handler.wfile.write(resp_data)


class HttpContext:
    def __init__(self, handler: BaseHTTPRequestHandler):
        self.request = Request(handler)
        self.response = Response(handler)
        self.error = None


class Middleware:
    def handle(self, ctx: HttpContext) -> bool:
        raise NotImplementedError()


class ServerHeader(Middleware):
    def handle(self, ctx: HttpContext) -> bool:
        ctx.response.header("X-Server-Type", "500lines server (testonly)")
        return False


class NotFound(Middleware):
    def handle(self, ctx: HttpContext) -> bool:
        ctx.response.status(404).html("<h1>File Not Found</h1>")
        return True


class Index(Middleware):
    def handle(self, ctx: HttpContext) -> bool:
        if ctx.request.path == "/":
            if ctx.request.query_string("err", "0") == "1":
                raise Exception("test error")
            else:
                ctx.response.html("<h1>Index</h1>")
            return True
        return False


class GenericError(Middleware):
    def handle(self, ctx: HttpContext) -> bool:
        if ctx.error:
            logging.getLogger("server").error(str(ctx.error))
        ctx.response.status(500).html("<h1>Internal Server Error</h1>")
        return True


def main():
    addr = ("", 8080)
    server = HTTPServer(addr, RequestDispatcher)
    server.serve_forever()


if __name__ == "__main__":
    main()
