import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export default function SoHHistoryChart({ points, kicker }) {
  return <section className="panel chart-panel">
    <div className="panel-heading"><div><div className="kicker">{kicker}</div><h2>Measured SOH and next-step estimate</h2></div><span className="unit">RELATIVE SOH · %</span></div>
    <div className="chart-box"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 12, right: 18, left: 2, bottom: 10 }}>
      <CartesianGrid stroke="#dfe8ea" strokeDasharray="3 4" vertical={false}/>
      <XAxis dataKey="cycle" tick={{ fill: "#667b84", fontSize: 13 }} axisLine={{ stroke: "#cbd8dc" }} tickLine={false}/>
      <YAxis domain={([a, b]) => [Math.floor(a - 2), Math.ceil(b + 2)]} tick={{ fill: "#667b84", fontSize: 13 }} axisLine={false} tickLine={false}/>
      <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #dce5e8", borderRadius: 7, color: "#18303b", fontSize: 14 }}/>
      <Line dataKey="measured_soh_percent" name="Measured SOH" stroke="#38515d" strokeWidth={2} dot={false} connectNulls/>
      <Line dataKey="predicted_next_soh_percent" name="Next scheduled estimate" stroke="#4169f5" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 5, fill: "#4169f5" }} connectNulls/>
    </LineChart></ResponsiveContainer></div>
  </section>;
}
