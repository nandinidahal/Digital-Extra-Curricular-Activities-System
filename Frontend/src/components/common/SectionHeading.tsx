interface Props { title: string; text?: string }

export default function SectionHeading({ title, text }: Props) {
  return (
    <div className="max-w-xl">
      <h2 className="text-3xl font-bold sm:text-4xl">{title}</h2>
      {text && <p className="mt-3 text-lg leading-relaxed opacity-70">{text}</p>}
    </div>
  );
}
