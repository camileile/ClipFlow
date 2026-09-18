const platforms = [
  {
    name: "YouTube",
    shortName: "YT",
    status: "Disponível",
    featured: true,
  },
  { name: "Instagram", shortName: "IG", status: "Em breve", featured: false },
  { name: "TikTok", shortName: "TK", status: "Disponível", featured: true },
  { name: "X", shortName: "X", status: "Em breve", featured: false },
];

export function Platforms() {
  return (
    <section className="mx-auto w-full max-w-5xl" aria-labelledby="platforms-title">
      <div className="mb-6 text-center">
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-accent">
          Um fluxo, várias fontes
        </p>
        <h2
          id="platforms-title"
          className="text-2xl font-semibold tracking-[-0.03em] text-foreground sm:text-3xl"
        >
          Plataformas planejadas
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {platforms.map((platform) => (
          <article
            key={platform.name}
            className={`rounded-2xl border p-4 transition duration-200 hover:-translate-y-0.5 sm:p-5 ${
              platform.featured
                ? "border-accent/35 bg-accent-soft"
                : "border-line bg-surface hover:border-line-strong"
            }`}
          >
            <div
              className={`mb-4 grid size-10 place-items-center rounded-xl text-xs font-black tracking-tight ${
                platform.featured
                  ? "bg-accent text-white shadow-accent"
                  : "border border-line bg-surface-elevated text-muted"
              }`}
              aria-hidden="true"
            >
              {platform.shortName}
            </div>
            <h3 className="font-semibold text-foreground">{platform.name}</h3>
            <p
              className={`mt-1 text-xs ${
                platform.featured ? "text-accent-strong" : "text-muted"
              }`}
            >
              {platform.status}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
