/** "Latest request wins": earlier async loads check this and discard their result. */
export function createLatestOnly() {
  let seq = 0;
  return {
    begin: () => ++seq,
    isCurrent: (token: number) => token === seq,
  };
}
