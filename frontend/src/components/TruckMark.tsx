import truckReference from '../assets/truck-linework.png'

/** Transparent linework derived from the supplied reference, bundled locally. */
export function TruckMark() {
  return <img className="truck-mark" src={truckReference} alt="重型商用车示意" width={1536} height={1024} draggable={false} />
}
