import { useEffect, useMemo, useState } from "react";
import axios from "axios";

import {
  TrendingUp,
  Sprout,
  MapPin,
  CalendarDays,
  Brain,
  Activity,
  BarChart3,
  Trophy,
  Globe,
} from "lucide-react";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import logo from "./assets/krushimitra-logo.png";
import translations from "./translations";

import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  // =====================================================
  // LANGUAGE
  // =====================================================

  const [language, setLanguage] = useState(() => {
    return (
      localStorage.getItem("krushimitra_language") ||
      "en"
    );
  });

  const t = translations[language];

  useEffect(() => {
    localStorage.setItem(
      "krushimitra_language",
      language
    );
  }, [language]);


  // =====================================================
  // DATA
  // =====================================================

  const [models, setModels] = useState([]);
  const [crops, setCrops] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [marketPrices, setMarketPrices] = useState([]);

  const [crop, setCrop] = useState("");
  const [market, setMarket] = useState("");
  const [variety, setVariety] = useState("");
  const [forecastDate, setForecastDate] = useState("");

  const [prediction, setPrediction] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [predictionHistory, setPredictionHistory] =
    useState(() => {
      try {
        const saved = localStorage.getItem(
          "krushimitra_prediction_history"
        );

        return saved
          ? JSON.parse(saved)
          : [];
      } catch {
        return [];
      }
    });


  // =====================================================
  // CROP DISPLAY NAME
  //
  // IMPORTANT:
  // `crop` remains the original English backend value.
  // Only the displayed text is translated.
  // =====================================================

  function getCropDisplayName(cropName) {
    if (!cropName) return "";

    return (
      t.cropNames?.[cropName] ||
      cropName
    );
  }


  // =====================================================
  // LOAD BACKEND DATA
  // =====================================================

  useEffect(() => {
    async function loadData() {
      try {
        setError("");

        const [
          cropResponse,
          marketResponse,
          modelResponse,
          priceResponse,
        ] = await Promise.all([
          axios.get(`${API_URL}/crops`),
          axios.get(`${API_URL}/markets`),
          axios.get(`${API_URL}/models`),
          axios.get(`${API_URL}/market-prices`),
        ]);

        const cropList =
          cropResponse.data.crops || [];

        const marketList =
          marketResponse.data.markets || [];

        const modelList =
          modelResponse.data.models || [];

        const priceList =
          priceResponse.data.prices || [];

        setCrops(cropList);
        setMarkets(marketList);
        setModels(modelList);
        setMarketPrices(priceList);

        if (cropList.length > 0) {
          setCrop(cropList[0]);
        }
      } catch (err) {
        console.error(err);

        setError(t.backendError);
      }
    }

    loadData();
  }, []);


  // =====================================================
  // VALID MARKETS
  // =====================================================

  const validMarkets = useMemo(() => {
    if (!crop) return [];

    return [
      ...new Set(
        models
          .filter(
            (item) =>
              String(item.crop).toLowerCase() ===
              String(crop).toLowerCase()
          )
          .map((item) => item.market)
      ),
    ];
  }, [models, crop]);


  useEffect(() => {
    if (!validMarkets.length) {
      setMarket("");
      return;
    }

    if (!validMarkets.includes(market)) {
      setMarket(validMarkets[0]);
    }
  }, [validMarkets, market]);


  // =====================================================
  // VALID VARIETIES
  // =====================================================

  const validVarieties = useMemo(() => {
    if (!crop || !market) return [];

    return [
      ...new Set(
        models
          .filter(
            (item) =>
              String(item.crop).toLowerCase() ===
                String(crop).toLowerCase() &&
              String(item.market).toLowerCase() ===
                String(market).toLowerCase()
          )
          .map(
            (item) => item.variety_used
          )
      ),
    ];
  }, [models, crop, market]);


  useEffect(() => {
    if (!validVarieties.length) {
      setVariety("");
      return;
    }

    if (!validVarieties.includes(variety)) {
      setVariety(validVarieties[0]);
    }
  }, [validVarieties, variety]);


  // =====================================================
  // LATEST MARKET PRICE
  // =====================================================

  const latestMarketPrice = useMemo(() => {
    if (!crop || !market || !variety) {
      return null;
    }

    const today = new Date();

    const matching = marketPrices.filter(
      (item) => {
        const itemDate = new Date(
          item.arrival_date
        );

        return (
          String(item.crop).toLowerCase() ===
            String(crop).toLowerCase() &&
          String(item.market).toLowerCase() ===
            String(market).toLowerCase() &&
          String(item.variety).toLowerCase() ===
            String(variety).toLowerCase() &&
          !Number.isNaN(
            itemDate.getTime()
          ) &&
          itemDate <= today
        );
      }
    );

    if (!matching.length) {
      return null;
    }

    return [...matching].sort(
      (a, b) =>
        new Date(b.arrival_date) -
        new Date(a.arrival_date)
    )[0];
  }, [
    marketPrices,
    crop,
    market,
    variety,
  ]);


  // =====================================================
  // MARKET COMPARISON
  // =====================================================

  const marketComparison = useMemo(() => {
    if (!crop) return [];

    const today = new Date();

    const cropPrices =
      marketPrices.filter((item) => {
        const itemDate = new Date(
          item.arrival_date
        );

        return (
          String(item.crop).toLowerCase() ===
            String(crop).toLowerCase() &&
          !Number.isNaN(
            itemDate.getTime()
          ) &&
          itemDate <= today
        );
      });

    const grouped = {};

    cropPrices.forEach((item) => {
      const marketName = item.market;

      if (!grouped[marketName]) {
        grouped[marketName] = [];
      }

      grouped[marketName].push(item);
    });

    return Object.entries(grouped)
      .map(
        ([marketName, entries]) => {
          const latest = [...entries].sort(
            (a, b) =>
              new Date(b.arrival_date) -
              new Date(a.arrival_date)
          )[0];

          return {
            market: marketName,
            modal_price: Number(
              latest.modal_price
            ),
            min_price: Number(
              latest.min_price
            ),
            max_price: Number(
              latest.max_price
            ),
            arrival_date:
              latest.arrival_date,
            variety: latest.variety,
          };
        }
      )
      .filter((item) =>
        Number.isFinite(
          item.modal_price
        )
      )
      .sort(
        (a, b) =>
          b.modal_price -
          a.modal_price
      );
  }, [marketPrices, crop]);


  const highestMarket =
    marketComparison[0] || null;


  // =====================================================
  // PREDICTION
  // =====================================================

  async function handlePrediction(event) {
    event.preventDefault();

    if (
      !crop ||
      !market ||
      !variety ||
      !forecastDate
    ) {
      setError(t.completeFields);
      return;
    }

    setLoading(true);
    setError("");
    setPrediction(null);

    try {
      const response =
        await axios.post(
          `${API_URL}/predict`,
          {
            // Backend receives English canonical name
            crop: crop,
            market: market,
            variety: variety,
            forecast_date:
              forecastDate,
          }
        );

      const result = response.data;

      setPrediction(result);

      setPredictionHistory(
        (previousHistory) => {
          const historyItem = {
            id: Date.now(),

            crop: result.crop,

            market: result.market,

            variety_used:
              result.variety_used,

            forecast_date:
              result.forecast_date,

            predicted_price:
              result.predicted_price,

            confidence_score:
              result.confidence_score,

            confidence_level:
              result.confidence_level,

            trend: result.trend,

            selected_model:
              result.selected_model,
          };

          const updatedHistory = [
            historyItem,
            ...previousHistory,
          ].slice(0, 10);

          localStorage.setItem(
            "krushimitra_prediction_history",
            JSON.stringify(
              updatedHistory
            )
          );

          return updatedHistory;
        }
      );
    } catch (err) {
      console.error(err);

      const message =
        err.response?.data?.detail ||
        t.predictionFailed;

      setError(
        typeof message === "string"
          ? message
          : JSON.stringify(message)
      );
    } finally {
      setLoading(false);
    }
  }


  // =====================================================
  // CLEAR HISTORY
  // =====================================================

  function clearPredictionHistory() {
    localStorage.removeItem(
      "krushimitra_prediction_history"
    );

    setPredictionHistory([]);
  }


  // =====================================================
  // FORECAST CHART
  // =====================================================

  const forecastChartData =
    prediction
      ? [
          {
            name: t.lower,
            price:
              prediction
                .estimated_price_range
                .lower,
          },

          {
            name: t.predicted,
            price:
              prediction.predicted_price,
          },

          {
            name: t.upper,
            price:
              prediction
                .estimated_price_range
                .upper,
          },
        ]
      : [];


  // =====================================================
  // FORMAT DATE
  // =====================================================

  function formatDate(value) {
    if (!value) return "N/A";

    const date = new Date(value);

    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return value;
    }

    return date.toLocaleDateString(
      language === "mr"
        ? "mr-IN"
        : language === "hi"
        ? "hi-IN"
        : "en-IN",
      {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }
    );
  }


  // =====================================================
  // UI
  // =====================================================

  return (
    <div className="app">

      {/* =================================================
          HEADER
      ================================================= */}

      <header className="header">

        <div className="brand">

          <img
            src={logo}
            alt="KrushiMitra AI"
            className="brand-logo"
          />

          <div className="brand-text">

            <h1>
              KrushiMitra AI
            </h1>

            <p>
              {t.footer}
            </p>

          </div>

        </div>


        <div className="header-right">

          {/* LANGUAGE */}

          <div className="language-selector">

            <Globe size={16} />

            <select
              value={language}
              onChange={(e) =>
                setLanguage(
                  e.target.value
                )
              }
            >

              <option value="en">
                English
              </option>

              <option value="mr">
                मराठी
              </option>

              <option value="hi">
                हिंदी
              </option>

            </select>

          </div>


          {/* STATUS */}

          <div className="status">

            <span className="status-dot"></span>

            {t.systemOnline}

          </div>

        </div>

      </header>


      <main className="container">

        {/* =================================================
            HERO
        ================================================= */}

        <section className="hero">

          <span className="eyebrow">
            {t.smartFarming}
          </span>

          <h2>

            {t.heroTitle}

            <span>
              {" "}
              {t.heroHighlight}
            </span>

          </h2>

          <p>
            {t.heroDescription}
          </p>

        </section>


        {/* =================================================
            MARKET COMPARISON
        ================================================= */}

        {crop &&
          marketComparison.length >
            0 && (

            <section className="comparison-section">

              <div className="comparison-header">

                <div className="section-heading">

                  <div className="heading-icon">
                    <BarChart3 size={22} />
                  </div>

                  <div>

                    <h3>
                      {t.marketComparison}
                    </h3>

                    <p>
                      {t.latestAvailablePrices}{" "}
                      <strong>
                        {getCropDisplayName(crop)}
                      </strong>
                    </p>

                  </div>

                </div>


                <div className="comparison-label">
                  {t.latestAvailable}
                </div>

              </div>


              {/* HIGHEST MARKET */}

              {highestMarket && (

                <div className="highest-market">

                  <div className="winner-icon">
                    <Trophy size={20} />
                  </div>

                  <div className="winner-text">

                    <span>
                      {t.highestPrice}
                    </span>

                    <strong>
                      {highestMarket.market}
                    </strong>

                  </div>

                  <div className="winner-price">

                    ₹
                    {highestMarket.modal_price.toLocaleString(
                      "en-IN"
                    )}

                    <small>
                      / {t.perQuintal}
                    </small>

                  </div>

                </div>

              )}


              {/* CHART */}

              <div className="comparison-chart">

                <ResponsiveContainer
                  width="100%"
                  height={340}
                >

                  <BarChart
                    data={
                      marketComparison
                    }
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                    />

                    <XAxis
                      dataKey="market"
                      tick={{
                        fontSize: 12,
                      }}
                    />

                    <YAxis
                      tick={{
                        fontSize: 11,
                      }}
                    />

                    <Tooltip
                      formatter={(value) => [
                        `₹${Number(
                          value
                        ).toLocaleString(
                          "en-IN"
                        )}`,
                        t.modalPrice,
                      ]}
                    />

                    <Bar
                      dataKey="modal_price"
                      fill="#1d6b3b"
                      radius={[
                        7,
                        7,
                        0,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>


              {/* MARKET CARDS */}

              <div className="comparison-grid">

                {marketComparison.map(
                  (item, index) => (

                    <div
                      className={`comparison-card ${
                        index === 0
                          ? "comparison-card-best"
                          : ""
                      }`}
                      key={
                        item.market
                      }
                    >

                      <div className="comparison-card-top">

                        <div className="market-icon">
                          <MapPin size={17} />
                        </div>

                        <span>

                          {index === 0
                            ? t.bestPrice
                            : `#${index + 1}`}

                        </span>

                      </div>

                      <h4>
                        {item.market}
                      </h4>

                      <strong>

                        ₹
                        {item.modal_price.toLocaleString(
                          "en-IN"
                        )}

                      </strong>

                      <p>
                        {t.modalPricePerQuintal}
                      </p>

                      <div className="comparison-range">

                        <span>
                          Min ₹
                          {item.min_price.toLocaleString(
                            "en-IN"
                          )}
                        </span>

                        <span>
                          Max ₹
                          {item.max_price.toLocaleString(
                            "en-IN"
                          )}
                        </span>

                      </div>

                      <small>

                        {t.updated}{" "}
                        {formatDate(
                          item.arrival_date
                        )}

                      </small>

                    </div>

                  )
                )}

              </div>

            </section>

          )}


        {/* =================================================
            PREDICTION FORM
        ================================================= */}

        <section className="prediction-card">

          <div className="section-heading">

            <div className="heading-icon">
              <Brain size={22} />
            </div>

            <div>

              <h3>
                {t.generateForecast}
              </h3>

              <p>
                {t.generateForecastDescription}
              </p>

            </div>

          </div>


          <form
            onSubmit={
              handlePrediction
            }
            className="form-grid"
          >

            {/* CROP */}

            <div className="field">

              <label>
                <Sprout size={16} />
                {t.crop}
              </label>

              <select
                value={crop}
                onChange={(e) =>
                  setCrop(
                    e.target.value
                  )
                }
                required
              >

                <option value="">
                  {t.selectCrop}
                </option>

                {crops.map(
                  (item) => (

                    <option
                      key={item}
                      value={item}
                    >
                      {getCropDisplayName(
                        item
                      )}
                    </option>

                  )
                )}

              </select>

            </div>


            {/* MARKET */}

            <div className="field">

              <label>
                <MapPin size={16} />
                {t.market}
              </label>

              <select
                value={market}
                onChange={(e) =>
                  setMarket(
                    e.target.value
                  )
                }
                disabled={!crop}
                required
              >

                <option value="">
                  {t.selectMarket}
                </option>

                {validMarkets.map(
                  (item) => (

                    <option
                      key={item}
                      value={item}
                    >
                      {item}
                    </option>

                  )
                )}

              </select>

            </div>


            {/* VARIETY */}

            <div className="field">

              <label>
                <Sprout size={16} />
                {t.variety}
              </label>

              <select
                value={variety}
                onChange={(e) =>
                  setVariety(
                    e.target.value
                  )
                }
                disabled={!market}
                required
              >

                <option value="">
                  {t.selectVariety}
                </option>

                {validVarieties.map(
                  (item) => (

                    <option
                      key={item}
                      value={item}
                    >
                      {item}
                    </option>

                  )
                )}

              </select>

            </div>


            {/* DATE */}

            <div className="field">

              <label>
                <CalendarDays size={16} />
                {t.forecastDate}
              </label>

              <input
                type="date"
                value={forecastDate}
                onChange={(e) =>
                  setForecastDate(
                    e.target.value
                  )
                }
                required
              />

            </div>


            {/* BUTTON */}

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
                ? t.generating
                : t.predictPrice}

            </button>

          </form>


          {error && (
            <div className="error">
              {error}
            </div>
          )}

        </section>


        {/* =================================================
            LATEST MARKET PRICE
        ================================================= */}

        {crop &&
          market &&
          variety &&
          latestMarketPrice && (

            <section className="market-price-section">

              <div className="section-heading">

                <div className="heading-icon">
                  <Activity size={22} />
                </div>

                <div>

                  <h3>
                    {t.latestMarketPrice}
                  </h3>

                  <p>
                    {getCropDisplayName(crop)} •{" "}
                    {market} •{" "}
                    {variety}
                  </p>

                </div>

              </div>


              <div className="metrics">

                <div className="metric main-metric">

                  <span>
                    {t.currentModalPrice}
                  </span>

                  <strong>

                    ₹
                    {Number(
                      latestMarketPrice.modal_price
                    ).toLocaleString(
                      "en-IN"
                    )}

                  </strong>

                  <small>
                    {t.perQuintal}
                  </small>

                </div>


                <div className="metric">

                  <span>
                    {t.minimumPrice}
                  </span>

                  <strong>

                    ₹
                    {Number(
                      latestMarketPrice.min_price
                    ).toLocaleString(
                      "en-IN"
                    )}

                  </strong>

                </div>


                <div className="metric">

                  <span>
                    {t.maximumPrice}
                  </span>

                  <strong>

                    ₹
                    {Number(
                      latestMarketPrice.max_price
                    ).toLocaleString(
                      "en-IN"
                    )}

                  </strong>

                </div>


                <div className="metric">

                  <span>
                    {t.arrivalDate}
                  </span>

                  <strong>

                    {formatDate(
                      latestMarketPrice.arrival_date
                    )}

                  </strong>

                </div>

              </div>

            </section>

          )}


        {/* =================================================
            PREDICTION RESULT
        ================================================= */}

        {prediction && (

          <section className="results">

            <div className="results-title">

              <div>

                <span className="eyebrow">
                  {t.aiForecast}
                </span>

                <h3>

                  {getCropDisplayName(
                    prediction.crop
                  )}

                  {" — "}

                  {prediction.market}

                </h3>

                <p>

                  {prediction.variety_used}
                  {" • "}
                  {formatDate(
                    prediction.forecast_date
                  )}

                </p>

              </div>


              <div className="confidence">

                <span>
                  {t.confidence}
                </span>

                <strong>
                  {prediction.confidence_score}%
                </strong>

                <small>
                  {prediction.confidence_level}
                </small>

              </div>

            </div>


            {/* RESULT METRICS */}

            <div className="metrics">

              <div className="metric main-metric">

                <span>
                  {t.predictedPrice}
                </span>

                <strong>

                  ₹
                  {Number(
                    prediction.predicted_price
                  ).toLocaleString(
                    "en-IN"
                  )}

                </strong>

                <small>
                  {t.perQuintal}
                </small>

              </div>


              <div className="metric">

                <span>
                  {t.lowerEstimate}
                </span>

                <strong>

                  ₹
                  {Number(
                    prediction
                      .estimated_price_range
                      .lower
                  ).toLocaleString(
                    "en-IN"
                  )}

                </strong>

              </div>


              <div className="metric">

                <span>
                  {t.upperEstimate}
                </span>

                <strong>

                  ₹
                  {Number(
                    prediction
                      .estimated_price_range
                      .upper
                  ).toLocaleString(
                    "en-IN"
                  )}

                </strong>

              </div>


              <div className="metric">

                <span>
                  {t.marketTrend}
                </span>

                <strong>
                  {prediction.trend}
                </strong>

              </div>

            </div>


            {/* FORECAST CHART */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h4>
                    {t.expectedRange}
                  </h4>

                  <p>
                    {t.forecastRange}
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

                <BarChart
                  data={
                    forecastChartData
                  }
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
                      `₹${Number(
                        value
                      ).toLocaleString(
                        "en-IN"
                      )}`,
                      t.price,
                    ]}
                  />

                  <Bar
                    dataKey="price"
                    fill="#1d6b3b"
                    radius={[
                      7,
                      7,
                      0,
                      0,
                    ]}
                  />

                </BarChart>

              </ResponsiveContainer>

            </div>


            {/* AI EXPLANATION */}

            <div className="explanation">

              <div className="explanation-title">

                <div className="ai-icon">
                  <Brain size={19} />
                </div>

                <div>

                  <h4>
                    {t.aiExplanation}
                  </h4>

                  <span>
                    {t.modelInsight}
                  </span>

                </div>

              </div>

              <p>
                {prediction.explanation}
              </p>

            </div>


            {prediction.warning_if_low_confidence && (

              <div className="warning">
                {prediction.warning_if_low_confidence}
              </div>

            )}

          </section>

        )}


        {/* =================================================
            HISTORY
        ================================================= */}

        {predictionHistory.length >
          0 && (

            <section className="history-section">

              <div className="history-header">

                <div className="section-heading">

                  <div className="heading-icon">
                    <Activity size={22} />
                  </div>

                  <div>

                    <h3>
                      {t.predictionHistory}
                    </h3>

                    <p>
                      {t.recentForecasts}
                    </p>

                  </div>

                </div>


                <button
                  className="clear-history-button"
                  onClick={
                    clearPredictionHistory
                  }
                  type="button"
                >
                  {t.clearHistory}
                </button>

              </div>


              <div className="history-list">

                {predictionHistory.map(
                  (item) => (

                    <div
                      className="history-item"
                      key={item.id}
                    >

                      <div className="history-main">

                        <div className="history-crop-icon">
                          <Sprout size={19} />
                        </div>

                        <div>

                          <strong>
                            {getCropDisplayName(
                              item.crop
                            )}
                          </strong>

                          <span>
                            {item.market} •{" "}
                            {item.variety_used}
                          </span>

                        </div>

                      </div>


                      <div className="history-price">

                        <span>
                          {t.predictedPrice}
                        </span>

                        <strong>

                          ₹
                          {Number(
                            item.predicted_price
                          ).toLocaleString(
                            "en-IN"
                          )}

                        </strong>

                      </div>


                      <div className="history-confidence">

                        <span>
                          {t.confidence}
                        </span>

                        <strong>
                          {item.confidence_score}%
                        </strong>

                      </div>


                      <div className="history-trend">
                        {item.trend}
                      </div>

                    </div>

                  )
                )}

              </div>

            </section>

          )}


        {/* =================================================
            DISCLAIMER
        ================================================= */}

        <section className="development-disclaimer">

          <div className="disclaimer-icon">
            ⚠
          </div>

          <div>

            <strong>
              {t.developmentPrototype}
            </strong>

            <p>
              {t.disclaimer}
            </p>

          </div>

        </section>

      </main>


      {/* FOOTER */}

      <footer>

        <div className="footer-brand">

          <img
            src={logo}
            alt="KrushiMitra AI"
          />

          <span>
            KrushiMitra AI
          </span>

        </div>

        <p>
          {t.footer}
        </p>

      </footer>

    </div>
  );
}

export default App;