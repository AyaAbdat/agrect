export type Phase = "mvp" | "phase2"

export type NavItem = {
  to: string
  labelKey: string
  phase: Phase
}

export const farmNav: NavItem[] = [
  { to: "/today", labelKey: "nav.today", phase: "mvp" },
  { to: "/blocks", labelKey: "nav.blocks", phase: "mvp" },
  { to: "/station", labelKey: "nav.station", phase: "mvp" },
  { to: "/season-timeline", labelKey: "nav.seasonTimeline", phase: "phase2" },
  { to: "/scores", labelKey: "nav.scores", phase: "phase2" },
  { to: "/compare", labelKey: "nav.compare", phase: "phase2" },
  { to: "/dashboards", labelKey: "nav.dashboards", phase: "phase2" },
  { to: "/week-review", labelKey: "nav.weekReview", phase: "phase2" },
  { to: "/harvest", labelKey: "nav.harvest", phase: "phase2" },
]

export const blockNav: { segment: string; labelKey: string; phase: Phase }[] = [
  { segment: "overview", labelKey: "nav.overview", phase: "mvp" },
  { segment: "weather", labelKey: "nav.weather", phase: "mvp" },
  { segment: "soil-water", labelKey: "nav.soilWater", phase: "mvp" },
  { segment: "stages", labelKey: "nav.stages", phase: "mvp" },
  { segment: "pests", labelKey: "nav.pests", phase: "phase2" },
  { segment: "maps", labelKey: "nav.maps", phase: "phase2" },
  { segment: "journal", labelKey: "nav.journal", phase: "phase2" },
  { segment: "setup", labelKey: "nav.setup", phase: "mvp" },
]

export const plansNav: NavItem[] = [
  { to: "/plans", labelKey: "nav.plans", phase: "phase2" },
  { to: "/team", labelKey: "nav.team", phase: "phase2" },
]

export const settingsNav = [
  {
    labelKey: "settings.personal",
    items: [
      { id: "profile", labelKey: "settings.profile" },
      { id: "units", labelKey: "settings.units" },
      { id: "ask", labelKey: "settings.ask" },
    ],
  },
  {
    labelKey: "settings.company",
    items: [
      { id: "team", labelKey: "settings.team" },
      { id: "inventories", labelKey: "settings.inventories" },
      { id: "ask-knowledge", labelKey: "settings.askKnowledge" },
    ],
  },
  {
    labelKey: "settings.farm",
    items: [
      { id: "workspace", labelKey: "settings.workspace" },
      { id: "farm-details", labelKey: "settings.farmDetails" },
      { id: "blocks", labelKey: "settings.blocks" },
    ],
  },
] as const

export function settingsPath(id: string): string {
  if (id === "workspace") return "/settings/workspace"
  return `/settings/${id}`
}

export function settingsTitleKey(section: string | undefined): string {
  for (const group of settingsNav) {
    for (const item of group.items) {
      if (item.id === section) return item.labelKey
    }
  }
  return "settings.title"
}
