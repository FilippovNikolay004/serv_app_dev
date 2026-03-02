class HomeController:
    def __init__(self, handler):
        self.handler = handler

    def do_GET(self):
        self.handler.send_response(200)
        self.handler.send_header("Content-Type", "text/html; charset=utf-8")
        self.handler.end_headers()

        html = """
        <h1>HTTP Server Working</h1>
        <img src="/img/Python.png" alt="logo" width="150" />
        <hr/>
        <button onclick="linkClick()">Send LINK request</button>
        <p id="out"></p>
        <script>
            function linkClick() {
                fetch("/", { method: "LINK" })
                .then(r => r.text())
                .then(t => document.getElementById('out').innerText = t);
            }
        </script>
        """
        self.handler.safe_write(html.encode("utf-8"))

    def do_LINK(self):
        self.handler.send_response(200)
        self.handler.send_header("Content-Type", "text/plain; charset=utf-8")
        self.handler.end_headers()
        self.handler.safe_write("LINK method response received!".encode("utf-8"))
