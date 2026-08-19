// Example Node.js function. Deploy this as the handler `main.handler`.

exports.handler = (request) => {
  const name = request.query.name || 'world';
  return { message: `hello, ${name}`, method: request.method };
};
