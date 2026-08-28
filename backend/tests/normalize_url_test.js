// Unit test for normalizeBackendUrl behavior (pure function, no react)
function normalizeBackendUrl(raw) {
  if (!raw || typeof raw !== "string") return "";
  const match = raw.match(/https?:\/\/[^\s"']+/i);
  const cleaned = match ? match[0] : raw.trim();
  return cleaned.replace(/\/+$/, "");
}

const cases = [
  ["REACT_APP_BACKEND_URL=https://x.com", "https://x.com"],
  ["https://x.com/", "https://x.com"],
  ["https://x.com", "https://x.com"],
  ["  https://api.example.com/api/  ", "https://api.example.com/api"],
  ["", ""],
  [undefined, ""],
  [null, ""],
  ["not-a-url", "not-a-url"],
  ["REACT_APP_BACKEND_URL=https://foo.up.railway.app/", "https://foo.up.railway.app"],
];

let failed = 0;
for (const [input, expected] of cases) {
  const got = normalizeBackendUrl(input);
  const ok = got === expected;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"} | input=${JSON.stringify(input)} expected=${JSON.stringify(expected)} got=${JSON.stringify(got)}`);
}
console.log(`\n${failed === 0 ? "ALL PASSED" : failed + " FAILED"}`);
process.exit(failed === 0 ? 0 : 1);
