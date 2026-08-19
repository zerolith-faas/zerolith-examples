*[Français](README.md)*

# timer

A countdown-timer web page, in one Node.js function. Enter a duration and it counts down to
00:00.

**Live:** <https://timer-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/>

## What it demonstrates

The handler does exactly one thing: return a complete HTML page, with its CSS and script inline.
All the interactivity — the input, the countdown, the presets — runs **in the browser**, not on
the platform. So the function executes once per page load, and sleeps the rest of the time.

That is the cheapest possible profile on a platform billed by execution time: one very short
call, then nothing.

```js
exports.handler = (request) => {
  return [200, PAGE, { 'content-type': 'text/html; charset=utf-8' }];
};
```

The `[status, body, headers]` array is the return shape that lets you set the `content-type` —
without it a string would be served as `text/plain` and the browser would display the HTML
instead of rendering it.

## Deploying

Runtime `nodejs24` (`nodejs20` and `nodejs22` work too), handler `main.handler`, no environment
variables, no query parameters. The function returns the same page on any path.
