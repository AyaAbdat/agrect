import { useQuery } from "@tanstack/react-query"
import L from "leaflet"
import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { MapContainer, Polygon, TileLayer, Tooltip, useMap, ZoomControl } from "react-leaflet"
import { useAuth } from "../../app/auth"
import { Button } from "@/components/ui/button"
import { apiGet } from "../../lib/api"
import type { GeoLine, GeoPolygon, MapGeometry } from "./geometry"
import markerIcon from "leaflet/dist/images/marker-icon.png"
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png"
import markerShadow from "leaflet/dist/images/marker-shadow.png"
import "leaflet/dist/leaflet.css"
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css"
import "@geoman-io/leaflet-geoman-free"

const iconProto = L.Icon.Default.prototype as L.Icon.Default & {
  _getIconUrl?: string
}
delete iconProto._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
const ATTRIBUTION =
  "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"

const OUTLINE_STYLE: L.PathOptions = {
  color: "#D8F3DC",
  weight: 2,
  fillColor: "#1B4332",
  fillOpacity: 0.2,
}

const LINE_STYLE: L.PathOptions = {
  color: "#FFFFFF",
  weight: 3,
}

const POLYGON_DRAW = {
  snappable: false,
  allowSelfIntersection: false,
  tooltips: false,
  cursorMarker: false,
  pathOptions: OUTLINE_STYLE,
  templineStyle: { color: "#D8F3DC", weight: 2 },
  hintlineStyle: { color: "#D8F3DC", weight: 2, dashArray: "4 6" },
}

const LINE_DRAW = {
  snappable: false,
  allowSelfIntersection: true,
  tooltips: false,
  cursorMarker: false,
  continueDrawing: false,
  pathOptions: LINE_STYLE,
  templineStyle: { color: "#FFFFFF", weight: 3 },
  hintlineStyle: { color: "#FFFFFF", weight: 2, dashArray: "4 6" },
}

type DrawTool = "outline" | "row"
type ShapeKind = "outline" | "row"

type PmLayer = L.Layer & {
  pm?: { enable: (options?: { allowSelfIntersection?: boolean }) => void }
  setStyle?: (style: L.PathOptions) => void
  toGeoJSON: (precision?: number) => GeoJSON.Feature
}

type PmApi = {
  setGlobalOptions: (options: object) => void
  enableDraw: (shape: "Polygon" | "Line", options?: object) => void
  disableDraw: () => void
  Draw: {
    Line: {
      enabled: () => boolean
      _finishShape: () => void
      _layer?: L.Layer
    }
  }
}

export type MapBlock = {
  id: string
  name: string
  outline: GeoPolygon | null
}

type SatelliteMapProps = {
  height: number
  blocks?: MapBlock[]
  onBlockClick?: (id: string) => void
  drawing?: boolean
  initial?: MapGeometry
  onChange?: (value: MapGeometry) => void
}

type FarmPoint = {
  lat: string | number | null
  lon: string | number | null
}

function parseCoord(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function geomanOf(map: L.Map): PmApi {
  return (map as L.Map & { pm: PmApi }).pm
}

function asPmLayer(layer: L.Layer): PmLayer | null {
  if (!("toGeoJSON" in layer) || typeof layer.toGeoJSON !== "function") return null
  return layer as PmLayer
}

function readPolygon(layer: PmLayer): GeoPolygon | null {
  const geometry = layer.toGeoJSON(8).geometry
  if (geometry.type !== "Polygon") return null
  return {
    type: "Polygon",
    coordinates: geometry.coordinates.map((ring) =>
      ring.map((position) => [position[0], position[1]] as [number, number]),
    ),
  }
}

function readLine(layer: PmLayer): GeoLine | null {
  const geometry = layer.toGeoJSON(8).geometry
  if (geometry.type !== "LineString") return null
  return {
    type: "LineString",
    coordinates: geometry.coordinates.map(
      (position) => [position[0], position[1]] as [number, number],
    ),
  }
}

function ringLatLngs(ring: [number, number][]): [number, number][] {
  return ring.map(([lon, lat]) => [lat, lon])
}

function polygonFromGeo(geo: GeoPolygon): L.Polygon {
  return L.polygon(
    geo.coordinates.map((ring) => ring.map(([lon, lat]) => L.latLng(lat, lon))),
    OUTLINE_STYLE,
  )
}

function lineFromGeo(geo: GeoLine): L.Polyline {
  return L.polyline(
    geo.coordinates.map(([lon, lat]) => L.latLng(lat, lon)),
    LINE_STYLE,
  )
}

const pillClass =
  "inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold shadow-sm"

function DrawController({
  tool,
  undoTick,
  initial,
  onChange,
  onOutline,
  onFinished,
}: {
  tool: DrawTool | null
  undoTick: number
  initial?: MapGeometry
  onChange?: (value: MapGeometry) => void
  onOutline: (present: boolean) => void
  onFinished: () => void
}) {
  const map = useMap()
  const outlineRef = useRef<PmLayer | null>(null)
  const lineRef = useRef<PmLayer | null>(null)
  const historyRef = useRef<ShapeKind[]>([])
  const onChangeRef = useRef(onChange)
  const onOutlineRef = useRef(onOutline)
  const onFinishedRef = useRef(onFinished)
  const undoRef = useRef<() => void>(() => {})
  const initialRef = useRef(initial)
  onChangeRef.current = onChange
  onOutlineRef.current = onOutline
  onFinishedRef.current = onFinished

  useEffect(() => {
    const pm = geomanOf(map)
    pm.setGlobalOptions({
      snappable: false,
      allowSelfIntersection: false,
      tooltips: false,
    })

    function emit() {
      const outline = outlineRef.current ? readPolygon(outlineRef.current) : null
      const rowLine = lineRef.current ? readLine(lineRef.current) : null
      onChangeRef.current?.({ outline, row_line: rowLine })
      onOutlineRef.current(outline !== null)
    }

    function adopt(kind: ShapeKind, layer: L.Layer, silent: boolean) {
      const path = asPmLayer(layer)
      if (path === null) return
      if (kind === "outline") {
        if (outlineRef.current && outlineRef.current !== path) outlineRef.current.remove()
        historyRef.current = historyRef.current.filter((item) => item !== "outline")
        path.setStyle?.(OUTLINE_STYLE)
        outlineRef.current = path
      } else {
        if (lineRef.current && lineRef.current !== path) lineRef.current.remove()
        historyRef.current = historyRef.current.filter((item) => item !== "row")
        path.setStyle?.(LINE_STYLE)
        lineRef.current = path
      }
      if (!map.hasLayer(path)) path.addTo(map)
      path.pm?.enable({ allowSelfIntersection: false })
      path.off("pm:edit", emit)
      path.on("pm:edit", emit)
      historyRef.current.push(kind)
      if (silent) onOutlineRef.current(outlineRef.current !== null)
      else emit()
    }

    function onCreate(event: L.LeafletEvent) {
      const created = event as L.LeafletEvent & { shape?: string; layer?: L.Layer }
      if (created.layer === undefined) return
      if (created.shape === "Polygon") adopt("outline", created.layer, false)
      if (created.shape === "Line") adopt("row", created.layer, false)
      onFinishedRef.current()
    }

    undoRef.current = () => {
      const last = historyRef.current.pop()
      if (last === "outline" && outlineRef.current) {
        outlineRef.current.remove()
        outlineRef.current = null
      } else if (last === "row" && lineRef.current) {
        lineRef.current.remove()
        lineRef.current = null
      }
      emit()
    }

    map.on("pm:create", onCreate)
    const seeded = initialRef.current
    if (seeded?.outline) adopt("outline", polygonFromGeo(seeded.outline), true)
    if (seeded?.row_line) adopt("row", lineFromGeo(seeded.row_line), true)

    return () => {
      map.off("pm:create", onCreate)
      outlineRef.current?.remove()
      lineRef.current?.remove()
      outlineRef.current = null
      lineRef.current = null
      historyRef.current = []
      pm.disableDraw()
    }
  }, [map])

  useEffect(() => {
    const pm = geomanOf(map)
    let working: L.Layer | undefined
    function finishLine() {
      window.setTimeout(() => {
        const draw = pm.Draw.Line
        if (draw.enabled()) draw._finishShape()
      }, 0)
    }
    if (tool === "outline") {
      pm.disableDraw()
      pm.enableDraw("Polygon", POLYGON_DRAW)
    } else if (tool === "row") {
      pm.disableDraw()
      pm.enableDraw("Line", LINE_DRAW)
      working = pm.Draw.Line._layer
      working?.on("pm:vertexadded", finishLine)
    } else {
      pm.disableDraw()
    }
    return () => {
      working?.off("pm:vertexadded", finishLine)
      pm.disableDraw()
    }
  }, [map, tool])

  useEffect(() => {
    if (undoTick === 0) return
    undoRef.current()
  }, [undoTick])

  return null
}

function BlockShapes({
  blocks,
  onBlockClick,
}: {
  blocks: MapBlock[]
  onBlockClick?: (id: string) => void
}) {
  return (
    <>
      {blocks.map((block) => {
        const ring = block.outline?.coordinates[0]
        if (ring === undefined) return null
        return (
          <Polygon
            key={block.id}
            positions={ringLatLngs(ring)}
            pathOptions={OUTLINE_STYLE}
            eventHandlers={{ click: () => onBlockClick?.(block.id) }}
          >
            <Tooltip permanent direction="center" className="block-name-tip">
              {block.name}
            </Tooltip>
          </Polygon>
        )
      })}
    </>
  )
}

export function SatelliteMap({
  height,
  blocks = [],
  onBlockClick,
  drawing = false,
  initial,
  onChange,
}: SatelliteMapProps) {
  const { t, i18n } = useTranslation()
  const zoomAt = i18n.dir() === "rtl" ? "topleft" : "topright"
  const { currentFarmId } = useAuth()
  const farmQuery = useQuery({
    queryKey: ["farm", currentFarmId],
    queryFn: () => apiGet<FarmPoint>(`/v1/farms/${currentFarmId}`),
    enabled: currentFarmId !== null,
  })
  const [tool, setTool] = useState<DrawTool | null>(() =>
    drawing && initial?.outline == null ? "outline" : null,
  )
  const [undoTick, setUndoTick] = useState(0)
  const [hasOutline, setHasOutline] = useState(() => initial?.outline != null)
  const lat = parseCoord(farmQuery.data?.lat)
  const lon = parseCoord(farmQuery.data?.lon)
  const center = lat !== null && lon !== null ? ([lat, lon] as [number, number]) : null

  function chooseTool(next: DrawTool) {
    setTool((current) => (current === next ? null : next))
  }

  let body = (
    <div className="flex h-full items-center justify-center gap-3 px-6 text-center">
      <span
        className="size-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-pri"
        aria-hidden="true"
      />
      <p>{t("common.loading")}</p>
    </div>
  )
  if (farmQuery.isError) {
    body = (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <p>{t("common.loadError")}</p>
        <Button type="button" onClick={() => void farmQuery.refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    )
  } else if (farmQuery.isSuccess && center === null) {
    body = (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p>{t("blocks.noLocation")}</p>
      </div>
    )
  } else if (center !== null) {
    body = (
      <div dir="ltr" className="absolute inset-0 z-0">
        <MapContainer
          center={center}
          zoom={17}
          maxZoom={19}
          zoomControl={false}
          className="h-full w-full"
        >
          <TileLayer url={TILES} maxZoom={19} attribution={ATTRIBUTION} />
          <ZoomControl key={zoomAt} position={zoomAt} />
          {drawing ? (
            <DrawController
              tool={tool}
              undoTick={undoTick}
              initial={initial}
              onChange={onChange}
              onOutline={setHasOutline}
              onFinished={() => setTool(null)}
            />
          ) : (
            <BlockShapes blocks={blocks} onBlockClick={onBlockClick} />
          )}
        </MapContainer>
      </div>
    )
  }

  return (
    <div
      className="relative z-0 overflow-hidden rounded-[14px] border border-[#C9D3C7] bg-[#E7EEE6]"
      style={{ height }}
    >
      {body}
      <span className={`${pillClass} absolute start-3 top-3 z-[1000] bg-white text-text`}>
        {t("blocks.satellite")}
      </span>
      {drawing && center !== null ? (
        <div className="absolute end-3 top-3 z-[1000] flex gap-2">
          <button
            type="button"
            className={`${pillClass} ${tool === "outline" ? "bg-pri text-white" : "border border-[#C7D2C9] bg-white text-text"}`}
            aria-pressed={tool === "outline"}
            onClick={() => chooseTool("outline")}
          >
            {t("blocks.drawOutline")}
          </button>
          <button
            type="button"
            className={`${pillClass} ${tool === "row" ? "bg-pri text-white" : "border border-[#C7D2C9] bg-white text-text"}`}
            aria-pressed={tool === "row"}
            onClick={() => chooseTool("row")}
          >
            {t("blocks.drawRowLine")}
          </button>
          <button
            type="button"
            className={`${pillClass} border border-[#C7D2C9] bg-white text-text`}
            onClick={() => setUndoTick((value) => value + 1)}
          >
            {t("blocks.undo")}
          </button>
        </div>
      ) : null}
      {drawing && center !== null && !hasOutline ? (
        <p className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center px-16 text-center">
          <span className="max-w-[420px] rounded-xl bg-white/90 px-4 py-3 text-[13px] text-text">
            {t("blocks.drawHint")}
          </span>
        </p>
      ) : null}
    </div>
  )
}
