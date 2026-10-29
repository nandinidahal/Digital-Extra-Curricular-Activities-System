export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="container-page py-20">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="mt-3 text-ink/70">This page is not built yet.</p>
    </section>
  );
}
