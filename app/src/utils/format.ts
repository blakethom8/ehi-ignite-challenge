type NumberFormatOptions = {
  fallback?: string;
  maxFractionDigits?: number;
  minAbsForScientific?: number;
  useGrouping?: boolean;
};

const DEFAULT_MAX_FRACTION_DIGITS = 2;

export function formatDisplayNumber(
  value: number | string | null | undefined,
  options: NumberFormatOptions = {},
): string {
  const {
    fallback = "-",
    maxFractionDigits = DEFAULT_MAX_FRACTION_DIGITS,
    minAbsForScientific = 0.01,
    useGrouping = true,
  } = options;

  if (value == null) return fallback;
  const numericValue = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numericValue)) return String(value);
  if (numericValue === 0) return "0";

  const absolute = Math.abs(numericValue);
  if (absolute < minAbsForScientific) {
    return new Intl.NumberFormat("en-US", {
      maximumSignificantDigits: 2,
      useGrouping,
    }).format(numericValue);
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: maxFractionDigits,
    useGrouping,
  }).format(numericValue);
}

export function formatSignedDisplayNumber(
  value: number | string | null | undefined,
  options: NumberFormatOptions = {},
): string {
  if (value == null) return options.fallback ?? "-";
  const numericValue = typeof value === "string" ? Number(value) : value;
  const formatted = formatDisplayNumber(value, options);
  return Number.isFinite(numericValue) && numericValue > 0 ? `+${formatted}` : formatted;
}

export function formatMeasurement(
  value: number | string | null | undefined,
  unit: string | null | undefined,
  options: NumberFormatOptions = {},
): string {
  const formatted = formatDisplayNumber(value, options);
  return formatted === (options.fallback ?? "-") || !unit ? formatted : `${formatted} ${unit}`;
}
