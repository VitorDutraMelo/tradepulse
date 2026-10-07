export type Direction = "CALL" | "PUT" | "NEUTRO";
export type Timeframe = "1m" | "5m" | "15m" | "1h";
export interface Asset { symbol:string; flag:string; price:string; change:number; signal:Direction; score:number|null }
export interface Candle { time:string; open:number; high:number; low:number; close:number; volume:number }
export interface MarketSignal { id:string; asset:string; timeframe:Timeframe; direction:Direction; score:number; time:string; pattern:string; confirmations:number; result:"WIN"|"LOSS"|"PENDING" }
