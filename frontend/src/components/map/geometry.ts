export type GeoPolygon = {
  type: "Polygon"
  coordinates: [number, number][][]
}

export type GeoLine = {
  type: "LineString"
  coordinates: [number, number][]
}

export type MapGeometry = {
  outline: GeoPolygon | null
  row_line: GeoLine | null
}
