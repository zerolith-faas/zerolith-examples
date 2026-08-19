"""Example Python function. Deploy this as the handler `main.handler`."""


def handler(request):
    name = request.query.get("name", "world")
    return {"message": f"hello, {name}", "method": request.method}
