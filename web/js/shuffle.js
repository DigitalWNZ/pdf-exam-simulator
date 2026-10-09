/** Fisher–Yates shuffle; returns a new array. rng() must return [0, 1). */
export function fisherYates(arr, rng = Math.random) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function sampleWithoutReplacement(arr, n, rng = Math.random) {
  return fisherYates(arr, rng).slice(0, Math.min(n, arr.length));
}
