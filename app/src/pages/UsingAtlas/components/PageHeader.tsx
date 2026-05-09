interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}

export function PageHeader({ eyebrow = "Using Atlas", title, subtitle }: PageHeaderProps) {
  return (
    <header className="mb-8 border-b border-[#e7eaf2] pb-7">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5b76fe]">
        {eyebrow}
      </p>
      <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-[#1d2433]">
        {title}
      </h1>
      {subtitle && (
        <p className="mt-2.5 text-base leading-relaxed text-[#4a5168]">{subtitle}</p>
      )}
    </header>
  );
}
