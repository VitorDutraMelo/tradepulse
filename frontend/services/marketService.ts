import { ASSETS, candleSeries } from "@/data/mockData"; import type { Timeframe } from "@/types/market";
const delay=(ms=250)=>new Promise(r=>setTimeout(r,ms)); export const marketService={async getAssets(){await delay();return ASSETS},async getCandles(symbol:string,timeframe:Timeframe){await delay();return candleSeries(symbol,timeframe)}};
