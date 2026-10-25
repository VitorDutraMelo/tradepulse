import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";

export const app = express();

app.use(helmet());
app.use(
  cors({
    origin: env.FRONTEND_ORIGIN,
  }),
);
app.use(express.json());

app.get("/api/v1/health", (_request, response) => {
  response.status(200).json({
    status: "ok",
    service: "tradepulse-backend",
  });
});