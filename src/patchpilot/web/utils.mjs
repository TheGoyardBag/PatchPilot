export function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
export function scoreLabel(value) { return value == null ? '—' : Number(value).toFixed(3); }
export function testLabel(value) { return value ? `${value.passed}/${value.tests} passed` : 'Policy blocked'; }
export function statusClass(status) { return ['approved','passed'].includes(status) ? 'good' : ['failed','rejected','interrupted'].includes(status) ? 'bad' : 'neutral'; }
export function parseSSE(text) {
  return text.split(/\r?\n\r?\n/).filter(Boolean).map(block => {
    let event='message',id=null,data=[];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) event=line.slice(6).trim();
      if (line.startsWith('id:')) id=line.slice(3).trim();
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    return data.length ? {event,id,data:JSON.parse(data.join('\n'))} : null;
  }).filter(Boolean);
}
export function diffClass(line) {
  if (line.startsWith('+++') || line.startsWith('---')) return 'diff-file';
  if (line.startsWith('@@')) return 'diff-hunk';
  if (line.startsWith('+')) return 'diff-add';
  if (line.startsWith('-')) return 'diff-remove';
  return 'diff-context';
}
