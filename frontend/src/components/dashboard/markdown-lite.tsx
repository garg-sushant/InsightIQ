// Renders the small markdown subset our prompts produce: headings, bold,
// italics, and bullet lists. Deliberately not a full markdown parser — the
// AI narrative is generated from constrained prompts, so this covers exactly
// what shows up.
function inline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*.+?\*\*|_.+?_)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("_") && part.endsWith("_")) {
      return <em key={index} className="text-muted-foreground">{part.slice(1, -1)}</em>;
    }
    return <span key={index}>{part}</span>;
  });
}

export function MarkdownLite({ content }: { content: string }) {
  const lines = content.split("\n").filter((line) => line.trim().length > 0);

  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (/^#{1,6}\s+/.test(trimmed)) {
          return (
            <p key={index} className="pt-1 font-semibold">
              {inline(trimmed.replace(/^#{1,6}\s+/, ""))}
            </p>
          );
        }
        if (/^[-*+]\s+/.test(trimmed)) {
          return (
            <div key={index} className="flex gap-2 pl-1">
              <span className="text-muted-foreground">•</span>
              <p>{inline(trimmed.replace(/^[-*+]\s+/, ""))}</p>
            </div>
          );
        }
        return <p key={index}>{inline(trimmed)}</p>;
      })}
    </div>
  );
}
