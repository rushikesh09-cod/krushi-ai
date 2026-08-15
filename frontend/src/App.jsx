import { useEffect, useMemo, useState } from "react";
import axios from "axios";

import {
  TrendingUp,
  Sprout,
  MapPin,
  CalendarDays,
  Brain,
  Activity,
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [models, setModels] = useState([]);
  const [crops, setCrops] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [marketPrices, setMarketPrices] = useState([]);

  const [crop, setCrop] = useState("");
  const [market, setMarket] = useState("");
  const [variety, setVariety] = useState("");

  const [forecastDate, setForecastDate] = useState("2026-08-22");

  const [prediction, setPrediction] = useState(null);

  const [loading, setLoading] = useState(false);
  const [loadingMarketPrice, setLoadingMarketPrice] = useState(false);

  const [error, setError] = useState("");

  // --------------------------------------------------
  // Load backend reference data
  // --------------------------------------------------

  useEffect(() => {
    async function loadData() {
      try {
        setError("");

        const [
          cropResponse,
          marketResponse,
          modelResponse,
          marketPriceResponse,
        ] = await Promise.all([
          axios.get(`${API_URL}/crops`),
          axios.get(`${API_URL}/markets`),
          axios.get(`${API_URL}/models`),
          axios.get(`${API_URL}/market-prices`),
        ]);

        const cropList = cropResponse.data.crops || [];
        const marketList = marketResponse.data.markets || [];
        const modelList = modelResponse.data.models || [];
        const priceList = marketPriceResponse.data.prices || [];

        setCrops(cropList);
        setMarkets(marketList);
        setModels(modelList);
        setMarketPrices(priceList);

        // Select first valid crop
        if (cropList.length > 0) {
          setCrop(cropList[0]);
        }
      } catch (err) {
        console.error("Backend connection error:", err);

        setError(
          "Unable to connect to the KrushiMitra AI backend. Make sure FastAPI is running on port 8000."
        );
      }
    }

    loadData();
  }, []);

  // --------------------------------------------------
  // Find valid markets for selected crop
  // --------------------------------------------------

  const validMarkets = useMemo(() => {
    if (!crop) return [];

    return [
      ...new Set(
        models
          .filter(
            (model) =>
              String(model.crop).toLowerCase() ===
              String(crop).toLowerCase()
          )
          .map((model) => model.market)
      ),
    ];
  }, [models, crop]);

  // --------------------------------------------------
  // Automatically select first valid market
  // --------------------------------------------------

  useEffect(() => {
    if (validMarkets.length === 0) {
      setMarket("");
      return;
    }

    if (!validMarkets.includes(market)) {
      setMarket(validMarkets[0]);
    }
  }, [validMarkets, market]);

  // --------------------------------------------------
  // Find valid variety for crop + market
  // --------------------------------------------------

  const validVarieties = useMemo(() => {
    if (!crop || !market) return [];

    return [
      ...new Set(
        models
          .filter(
            (model) =>
              String(model.crop).toLowerCase() ===
                String(crop).toLowerCase() &&
              String(model.market).toLowerCase() ===
                String(market).toLowerCase()
          )
          .map((model) => model.variety_used)
      ),
    ];
  }, [models, crop, market]);

  // --------------------------------------------------
  // Automatically select valid variety
  // --------------------------------------------------

  useEffect(() => {
    if (validVarieties.length === 0) {
      setVariety("");
      return;
    }

    if (!validVarieties.includes(variety)) {
      setVariety(validVarieties[0]);
    }
  }, [validVarieties, variety]);

  // --------------------------------------------------
  // Find latest available market price
  // --------------------------------------------------

  const latestMarketPrice = useMemo(() => {
    if (!crop || !market || !variety || marketPrices.length === 0) {
      return null;
    }

    const matchingPrices = marketPrices.filter((item) => {
      const cropMatch =
        String(item.crop).toLowerCase() === String(crop).toLowerCase();

      const marketMatch =
        String(item.market).toLowerCase() ===
        String(market).toLowerCase();

      const varietyMatch =
        String(item.variety).toLowerCase() ===
        String(variety).toLowerCase();

      return cropMatch && marketMatch && varietyMatch;
    });

    if (matchingPrices.length === 0) {
      return null;
    }

    // Sort by arrival date and take the newest record
    const sortedPrices = [...matchingPrices].sort(
      (a, b) =>
        new Date(b.arrival_date) -
        new Date(a.arrival_date)
    );

    return sortedPrices[0];
  }, [marketPrices, crop, market, variety]);

  // --------------------------------------------------
  // Prediction
  // --------------------------------------------------

  async function handlePrediction(event) {
    event.preventDefault();

    if (!crop || !market || !variety || !forecastDate) {
      setError("Please complete all fields.");
      return;
    }

    setLoading(true);
    setError("");
    setPrediction(null);

    try {
      const response = await axios.post(`${API_URL}/predict`, {
        crop,
        market,
        variety,
        forecast_date: forecastDate,
      });

      setPrediction(response.data);
    } catch (err) {
      console.error("Prediction error:", err);

      const message =
        err.response?.data?.detail ||
        "Prediction failed. Please check your inputs.";

      setError(
        typeof message === "string"
          ? message
          : JSON.stringify(message)
      );
    } finally {
      setLoading(false);
    }
  }

  // --------------------------------------------------
  // Chart data
  // --------------------------------------------------

  const chartData = prediction
    ? [
        {
          name: "Lower",
          price: prediction.estimated_price_range.lower,
        },
        {
          name: "Predicted",
          price: prediction.predicted_price,
        },
        {
          name: "Upper",
          price: prediction.estimated_price_range.upper,
        },
      ]
    : [];

  // --------------------------------------------------
  // Format date
  // --------------------------------------------------

  function formatDate(dateString) {
    if (!dateString) return "N/A";

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
      return dateString;
    }

    return date.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  // --------------------------------------------------
  // UI
  // --------------------------------------------------

  return (
    <div className="app">

      {/* Header */}
      <header className="header">

        <div className="brand">

          <div className="brand-icon">
            <Sprout size={28} />
          </div>

          <div>
            <h1>KrushiMitra AI</h1>

            <p>
              AI-Powered Agricultural Price Forecasting
            </p>
          </div>

        </div>

        <div className="status">
          <span className="status-dot"></span>
          AI System Online
        </div>

      </header>


      <main className="container">

        {/* Hero */}
        <section className="hero">

          <span className="eyebrow">
            SMART FARMING • MARKET INTELLIGENCE
          </span>

          <h2>
            Make smarter crop-selling decisions
            <span>
              {" "}with AI-powered price forecasts.
            </span>
          </h2>

          <p>
            Select a crop and market to view the latest
            available market price and generate an
            AI-powered price forecast.
          </p>

        </section>


        {/* Prediction Form */}
        <section className="prediction-card">

          <div className="section-heading">

            <div className="heading-icon">
              <Brain size={22} />
            </div>

            <div>
              <h3>Generate Price Forecast</h3>

              <p>
                Enter the crop and market information below.
              </p>
            </div>

          </div>


          <form
            onSubmit={handlePrediction}
            className="form-grid"
          >

            {/* Crop */}
            <div className="field">

              <label>
                <Sprout size={16} />
                Crop
              </label>

              <select
                value={crop}
                onChange={(e) =>
                  setCrop(e.target.value)
                }
                required
              >

                <option value="">
                  Select crop
                </option>

                {crops.map((item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                ))}

              </select>

            </div>


            {/* Market */}
            <div className="field">

              <label>
                <MapPin size={16} />
                Market
              </label>

              <select
                value={market}
                onChange={(e) =>
                  setMarket(e.target.value)
                }
                required
                disabled={!crop}
              >

                <option value="">
                  Select market
                </option>

                {validMarkets.map((item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                ))}

              </select>

            </div>


            {/* Variety */}
            <div className="field">

              <label>
                <Sprout size={16} />
                Variety
              </label>

              <select
                value={variety}
                onChange={(e) =>
                  setVariety(e.target.value)
                }
                required
                disabled={!market}
              >

                <option value="">
                  Select variety
                </option>

                {validVarieties.map((item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                ))}

              </select>

            </div>


            {/* Forecast Date */}
            <div className="field">

              <label>
                <CalendarDays size={16} />
                Forecast Date
              </label>

              <input
                type="date"
                value={forecastDate}
                onChange={(e) =>
                  setForecastDate(e.target.value)
                }
                required
              />

            </div>


            {/* Predict */}
            <button
              className="predict-button"
              type="submit"
              disabled={
                loading ||
                !crop ||
                !market ||
                !variety
              }
            >

              <TrendingUp size={20} />

              {loading
                ? "Generating..."
                : "Predict Price"}

            </button>

          </form>


          {error && (
            <div className="error">
              {error}
            </div>
          )}

        </section>


        {/* ------------------------------------------------
            Latest Market Price
        ------------------------------------------------ */}
        {crop && market && variety && (

          <section className="market-price-section">

            <div className="section-heading">

              <div className="heading-icon">
                <Activity size={22} />
              </div>

              <div>
                <h3>Latest Available Market Price</h3>

                <p>
                  Most recent market data available in the system.
                </p>
              </div>

            </div>


            {latestMarketPrice ? (

              <div className="metrics">

                {/* Modal Price */}
                <div className="metric main-metric">

                  <span>
                    Current Modal Price
                  </span>

                  <strong>
                    ₹
                    {Number(
                      latestMarketPrice.modal_price
                    ).toLocaleString("en-IN")}
                  </strong>

                  <small>
                    per quintal
                  </small>

                </div>


                {/* Minimum */}
                <div className="metric">

                  <span>
                    Minimum Price
                  </span>

                  <strong>
                    ₹
                    {Number(
                      latestMarketPrice.min_price
                    ).toLocaleString("en-IN")}
                  </strong>

                </div>


                {/* Maximum */}
                <div className="metric">

                  <span>
                    Maximum Price
                  </span>

                  <strong>
                    ₹
                    {Number(
                      latestMarketPrice.max_price
                    ).toLocaleString("en-IN")}
                  </strong>

                </div>


                {/* Arrival Date */}
                <div className="metric">

                  <span>
                    Latest Arrival Date
                  </span>

                  <strong>
                    {formatDate(
                      latestMarketPrice.arrival_date
                    )}
                  </strong>

                </div>

              </div>

            ) : (

              <div className="error">
                No market price data found for{" "}
                {crop} — {market} — {variety}.
              </div>

            )}

          </section>

        )}


        {/* ------------------------------------------------
            AI Forecast Results
        ------------------------------------------------ */}

        {prediction && (

          <section className="results">

            <div className="results-title">

              <div>

                <span className="eyebrow">
                  AI FORECAST RESULT
                </span>

                <h3>
                  {prediction.crop} —{" "}
                  {prediction.market}
                </h3>

                <p>
                  {prediction.variety_used} •{" "}
                  {prediction.forecast_date}
                </p>

              </div>


              <div className="confidence">

                <span>
                  Confidence
                </span>

                <strong>
                  {prediction.confidence_score}%
                </strong>

                <small>
                  {prediction.confidence_level}
                </small>

              </div>

            </div>


            {/* Forecast Metrics */}
            <div className="metrics">

              <div className="metric main-metric">

                <span>
                  Predicted Price
                </span>

                <strong>
                  ₹
                  {Number(
                    prediction.predicted_price
                  ).toLocaleString("en-IN")}
                </strong>

                <small>
                  per quintal
                </small>

              </div>


              <div className="metric">

                <span>
                  Lower Estimate
                </span>

                <strong>
                  ₹
                  {Number(
                    prediction.estimated_price_range.lower
                  ).toLocaleString("en-IN")}
                </strong>

              </div>


              <div className="metric">

                <span>
                  Upper Estimate
                </span>

                <strong>
                  ₹
                  {Number(
                    prediction.estimated_price_range.upper
                  ).toLocaleString("en-IN")}
                </strong>

              </div>


              <div className="metric">

                <span>
                  Market Trend
                </span>

                <strong>
                  {prediction.trend}
                </strong>

              </div>

            </div>


            {/* Chart */}
            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h4>
                    Expected Price Range
                  </h4>

                  <p>
                    AI-generated forecast range
                  </p>

                </div>

                <span className="model-badge">
                  {prediction.selected_model}
                </span>

              </div>


              <ResponsiveContainer
                width="100%"
                height={300}
              >

                <LineChart
                  data={chartData}
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="name"
                  />

                  <YAxis />

                  <Tooltip
                    formatter={(value) => [
                      `₹${Number(value).toLocaleString(
                        "en-IN"
                      )}`,
                      "Price",
                    ]}
                  />

                  <Line
                    type="monotone"
                    dataKey="price"
                    strokeWidth={3}
                    dot={{ r: 6 }}
                  />

                </LineChart>

              </ResponsiveContainer>

            </div>


            {/* Explanation */}
            <div className="explanation">

              <h4>
                AI Explanation
              </h4>

              <p>
                {prediction.explanation}
              </p>

            </div>


            {/* Warning */}
            {prediction.warning_if_low_confidence && (

              <div className="warning">
                {prediction.warning_if_low_confidence}
              </div>

            )}

          </section>

        )}

      </main>


      <footer>

        <p>
          KrushiMitra AI • AI-based agricultural
          market decision support
        </p>

      </footer>

    </div>
  );
}

export default App;