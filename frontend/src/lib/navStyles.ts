export const sectionLabelClass =
  "px-2.5 pb-[6px] pt-[14px] text-[10px] font-bold uppercase tracking-[0.1em] text-[#9CA3AF]"

export const crumbClass =
  "text-[11px] font-bold uppercase tracking-[0.12em] text-grn"

export function navItemClass(active: boolean): string {
  const base = "flex h-[30px] items-center rounded-lg px-2.5"
  if (active) return `${base} bg-mint font-bold text-pri`
  return `${base} font-medium hover:bg-[#F3F5F3]`
}

export const navDisabledClass =
  "flex h-[30px] items-center rounded-lg px-2.5 font-medium text-[#9CA3AF]"
