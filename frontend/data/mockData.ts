import type { Asset, Candle, MarketSignal, Timeframe } from "@/types/market";
export const ASSETS:Asset[]=[
 {symbol:"EUR/USD",flag:"🇪🇺",price:"1.08755",change:.01,signal:"CALL",score:82}, {symbol:"GBP/USD",flag:"🇬🇧",price:"1.34218",change:.08,signal:"CALL",score:76},
 {symbol:"AUD/USD",flag:"🇦🇺",price:"0.65721",change:-.12,signal:"PUT",score:68}, {symbol:"USD/JPY",flag:"🇺🇸",price:"149.824",change:.05,signal:"CALL",score:71},
 {symbol:"BTC/USD",flag:"₿",price:"64,218",change:-.31,signal:"PUT",score:64}, {symbol:"ETH/USD",flag:"◆",price:"3,421",change:.17,signal:"CALL",score:67},
 {symbol:"Gold",flag:"●",price:"2,634.2",change:-.09,signal:"NEUTRO",score:null}
];
export const SIGNALS:MarketSignal[]=[
 {id:"s1",asset:"EUR/USD",timeframe:"5m",direction:"CALL",score:82,time:"14:28",pattern:"Bullish Engulfing",confirmations:5,result:"WIN"},
 {id:"s2",asset:"GBP/USD",timeframe:"5m",direction:"CALL",score:76,time:"14:17",pattern:"Morning Star",confirmations:4,result:"WIN"},
 {id:"s3",asset:"AUD/USD",timeframe:"15m",direction:"PUT",score:68,time:"14:06",pattern:"Shooting Star",confirmations:4,result:"LOSS"},
 {id:"s4",asset:"USD/JPY",timeframe:"5m",direction:"CALL",score:71,time:"13:54",pattern:"Hammer",confirmations:4,result:"WIN"},
 {id:"s5",asset:"BTC/USD",timeframe:"1h",direction:"PUT",score:64,time:"13:42",pattern:"Bearish Engulfing",confirmations:3,result:"LOSS"},
 {id:"s6",asset:"ETH/USD",timeframe:"15m",direction:"CALL",score:67,time:"13:31",pattern:"Inverted Hammer",confirmations:4,result:"PENDING"}
];
export const HISTORY=Array.from({length:12},(_,i)=>{const s=SIGNALS[i%SIGNALS.length];return {...s,id:`h${i}`,date:`${String(26-(i%6)).padStart(2,"0")}/09/2026`,entry:i%2?"1.34210":"1.08750",stop:i%2?"1.34020":"1.08690",target:i%2?"1.34590":"1.08830"}});
export const BACKTEST_CURVE=Array.from({length:30},(_,i)=>({day:`${i+1}/08`,value:Number((-4+i*.9+Math.sin(i*.8)*3).toFixed(1))}));
export function candleSeries(symbol:string,timeframe:Timeframe):Candle[]{let seed=[...symbol].reduce((n,c)=>n+c.charCodeAt(0),0)+timeframe.length;let price=symbol.includes("BTC")?64200:symbol==="USD/JPY"?149.8:symbol==="GBP/USD"?1.34:1.087;const scale=price>100?30:.001;return Array.from({length:34},(_,i)=>{const wave=Math.sin((i+seed)*.55)*scale*.55;const trend=(i-17)*scale*.012;const open=price+wave+trend;const close=open+(Math.sin((i+seed)*1.37)*scale*.34);price=close;return {time:`${10+Math.floor(i/7)}:${String(i%7*8).padStart(2,"0")}`,open,close,high:Math.max(open,close)+scale*.2+(i%3)*scale*.05,low:Math.min(open,close)-scale*.2-(i%2)*scale*.06,volume:900+i*18}})}
