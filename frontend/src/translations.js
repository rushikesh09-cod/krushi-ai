const translations = {
  en: {
    language: "Language",
    systemOnline: "AI System Online",

    smartFarming: "SMART FARMING • MARKET INTELLIGENCE",
    heroTitle: "Make smarter crop-selling decisions",
    heroHighlight: "with AI-powered price forecasts.",
    heroDescription:
      "Compare available markets, inspect recent prices, and generate AI-powered crop price forecasts.",

    marketComparison: "Market Comparison",
    latestAvailable: "Latest Available Data",
    latestAvailablePrices:
      "Latest available modal prices across markets for",

    highestPrice: "Highest available modal price",
    bestPrice: "BEST PRICE",
    modalPrice: "Modal Price",
    modalPricePerQuintal: "Modal price / quintal",

    generateForecast: "Generate Price Forecast",
    generateForecastDescription:
      "Enter crop and market information to generate an AI forecast.",

    crop: "Crop",
    market: "Market",
    variety: "Variety",
    forecastDate: "Forecast Date",

    selectCrop: "Select crop",
    selectMarket: "Select market",
    selectVariety: "Select variety",

    predictPrice: "Predict Price",
    generating: "Generating...",

    latestMarketPrice: "Latest Available Market Price",
    currentModalPrice: "Current Modal Price",
    minimumPrice: "Minimum Price",
    maximumPrice: "Maximum Price",
    arrivalDate: "Arrival Date",
    perQuintal: "per quintal",

    aiForecast: "AI FORECAST RESULT",
    confidence: "Confidence",
    predictedPrice: "Predicted Price",
    lowerEstimate: "Lower Estimate",
    upperEstimate: "Upper Estimate",
    marketTrend: "Market Trend",

    expectedRange: "Expected Price Range",
    forecastRange: "AI-generated forecast range",

    aiExplanation: "AI Explanation",
    modelInsight: "Model-based market insight",

    predictionHistory: "Prediction History",
    recentForecasts: "Your recent AI-generated forecasts",
    clearHistory: "Clear History",

    developmentPrototype: "Development Prototype",

    disclaimer:
      "Predictions and market comparisons currently use development/sample data. They are intended for demonstration and decision-support purposes only. Actual market prices may vary because of supply, demand, weather, government policies, and other market conditions.",

    footer:
      "AI-based agricultural market decision support",

    updated: "Updated",
    lower: "Lower",
    predicted: "Predicted",
    upper: "Upper",
    price: "Price",

    backendError:
      "Unable to connect to the KrushiMitra AI backend. Make sure FastAPI is running on port 8000.",

    completeFields:
      "Please complete all fields.",

    predictionFailed:
      "Prediction failed. Please check your inputs.",

    cropNames: {
      Onion: "Onion",
      Potato: "Potato",
      Tomato: "Tomato",
      Wheat: "Wheat",
      Soybean: "Soybean",
      Maize: "Maize",
    },
  },

  mr: {
    language: "भाषा",
    systemOnline: "AI प्रणाली ऑनलाइन",

    smartFarming: "स्मार्ट शेती • बाजारपेठ माहिती",
    heroTitle: "पीक विक्रीसाठी अधिक चांगले निर्णय घ्या",
    heroHighlight: "AI आधारित किंमत अंदाजासह.",
    heroDescription:
      "उपलब्ध बाजारपेठांची तुलना करा, अलीकडील किंमती पहा आणि AI आधारित पीक किंमत अंदाज मिळवा.",

    marketComparison: "बाजारपेठ तुलना",
    latestAvailable: "उपलब्ध नवीनतम माहिती",
    latestAvailablePrices:
      "या पिकासाठी विविध बाजारपेठांमधील उपलब्ध नवीनतम मोडल किंमती:",

    highestPrice: "सर्वाधिक उपलब्ध मोडल किंमत",
    bestPrice: "सर्वोत्तम किंमत",
    modalPrice: "मोडल किंमत",
    modalPricePerQuintal: "मोडल किंमत / क्विंटल",

    generateForecast: "किंमत अंदाज तयार करा",
    generateForecastDescription:
      "AI अंदाज तयार करण्यासाठी पीक आणि बाजारपेठेची माहिती भरा.",

    crop: "पीक",
    market: "बाजारपेठ",
    variety: "वाण",
    forecastDate: "अंदाजाची तारीख",

    selectCrop: "पीक निवडा",
    selectMarket: "बाजारपेठ निवडा",
    selectVariety: "वाण निवडा",

    predictPrice: "किंमत अंदाज द्या",
    generating: "अंदाज तयार होत आहे...",

    latestMarketPrice: "उपलब्ध नवीनतम बाजारभाव",
    currentModalPrice: "सध्याची मोडल किंमत",
    minimumPrice: "किमान किंमत",
    maximumPrice: "कमाल किंमत",
    arrivalDate: "आवक तारीख",
    perQuintal: "प्रति क्विंटल",

    aiForecast: "AI किंमत अंदाज",
    confidence: "विश्वास पातळी",
    predictedPrice: "अंदाजित किंमत",
    lowerEstimate: "किमान अंदाज",
    upperEstimate: "कमाल अंदाज",
    marketTrend: "बाजाराचा कल",

    expectedRange: "अपेक्षित किंमत श्रेणी",
    forecastRange: "AI द्वारे तयार केलेली अंदाजित किंमत श्रेणी",

    aiExplanation: "AI स्पष्टीकरण",
    modelInsight: "मॉडेलवर आधारित बाजारपेठ माहिती",

    predictionHistory: "किंमत अंदाज इतिहास",
    recentForecasts: "तुमचे अलीकडील AI किंमत अंदाज",
    clearHistory: "इतिहास साफ करा",

    developmentPrototype: "विकासात्मक प्रोटोटाइप",

    disclaimer:
      "किंमत अंदाज आणि बाजारपेठ तुलना सध्या विकासात्मक/नमुना डेटावर आधारित आहेत. हे परिणाम प्रात्यक्षिक आणि निर्णय घेण्यास मदत करण्यासाठी आहेत. प्रत्यक्ष बाजारभाव पुरवठा, मागणी, हवामान, सरकारी धोरणे आणि इतर बाजारपेठेतील परिस्थितींनुसार बदलू शकतात.",

    footer: "AI आधारित कृषी बाजारपेठ निर्णय सहाय्य",

    updated: "अद्यतनित",
    lower: "किमान",
    predicted: "अंदाजित",
    upper: "कमाल",
    price: "किंमत",

    backendError:
      "KrushiMitra AI बॅकएंडशी कनेक्ट करता आले नाही. FastAPI पोर्ट 8000 वर चालू आहे याची खात्री करा.",

    completeFields:
      "कृपया सर्व माहिती भरा.",

    predictionFailed:
      "किंमत अंदाज तयार करता आला नाही. कृपया माहिती तपासा.",

    cropNames: {
      Onion: "कांदा",
      Potato: "बटाटा",
      Tomato: "टोमॅटो",
      Wheat: "गहू",
      Soybean: "सोयाबीन",
      Maize: "मका",
    },
  },

  hi: {
    language: "भाषा",
    systemOnline: "AI सिस्टम ऑनलाइन",

    smartFarming: "स्मार्ट खेती • बाजार जानकारी",
    heroTitle: "फसल बेचने के लिए बेहतर निर्णय लें",
    heroHighlight: "AI आधारित मूल्य पूर्वानुमान के साथ।",
    heroDescription:
      "उपलब्ध बाजारों की तुलना करें, हाल की कीमतें देखें और AI आधारित फसल मूल्य पूर्वानुमान प्राप्त करें।",

    marketComparison: "बाजार तुलना",
    latestAvailable: "नवीनतम उपलब्ध डेटा",
    latestAvailablePrices:
      "इस फसल के लिए विभिन्न बाजारों में उपलब्ध नवीनतम मोडल कीमतें:",

    highestPrice: "सबसे अधिक उपलब्ध मोडल कीमत",
    bestPrice: "सर्वोत्तम कीमत",
    modalPrice: "मोडल कीमत",
    modalPricePerQuintal: "मोडल कीमत / क्विंटल",

    generateForecast: "मूल्य पूर्वानुमान तैयार करें",
    generateForecastDescription:
      "AI पूर्वानुमान तैयार करने के लिए फसल और बाजार की जानकारी भरें।",

    crop: "फसल",
    market: "बाजार",
    variety: "किस्म",
    forecastDate: "पूर्वानुमान तारीख",

    selectCrop: "फसल चुनें",
    selectMarket: "बाजार चुनें",
    selectVariety: "किस्म चुनें",

    predictPrice: "कीमत का अनुमान लगाएं",
    generating: "पूर्वानुमान तैयार हो रहा है...",

    latestMarketPrice: "नवीनतम उपलब्ध बाजार मूल्य",
    currentModalPrice: "वर्तमान मोडल कीमत",
    minimumPrice: "न्यूनतम कीमत",
    maximumPrice: "अधिकतम कीमत",
    arrivalDate: "आवक तारीख",
    perQuintal: "प्रति क्विंटल",

    aiForecast: "AI मूल्य पूर्वानुमान",
    confidence: "विश्वास स्तर",
    predictedPrice: "अनुमानित कीमत",
    lowerEstimate: "न्यूनतम अनुमान",
    upperEstimate: "अधिकतम अनुमान",
    marketTrend: "बाजार का रुझान",

    expectedRange: "अपेक्षित मूल्य सीमा",
    forecastRange: "AI द्वारा तैयार अनुमानित मूल्य सीमा",

    aiExplanation: "AI स्पष्टीकरण",
    modelInsight: "मॉडल आधारित बाजार जानकारी",

    predictionHistory: "पूर्वानुमान इतिहास",
    recentForecasts: "आपके हाल के AI मूल्य पूर्वानुमान",
    clearHistory: "इतिहास साफ करें",

    developmentPrototype: "विकासात्मक प्रोटोटाइप",

    disclaimer:
      "पूर्वानुमान और बाजार तुलना वर्तमान में विकासात्मक/नमूना डेटा का उपयोग करते हैं। इनका उद्देश्य प्रदर्शन और निर्णय लेने में सहायता करना है। वास्तविक बाजार कीमतें आपूर्ति, मांग, मौसम, सरकारी नीतियों और अन्य बाजार परिस्थितियों के कारण अलग हो सकती हैं।",

    footer: "AI आधारित कृषि बाजार निर्णय सहायता",

    updated: "अपडेट किया गया",
    lower: "न्यूनतम",
    predicted: "अनुमानित",
    upper: "अधिकतम",
    price: "कीमत",

    backendError:
      "KrushiMitra AI बैकएंड से कनेक्ट नहीं हो सका। सुनिश्चित करें कि FastAPI पोर्ट 8000 पर चल रहा है।",

    completeFields:
      "कृपया सभी जानकारी भरें।",

    predictionFailed:
      "पूर्वानुमान तैयार नहीं हो सका। कृपया अपनी जानकारी जांचें।",

    cropNames: {
      Onion: "प्याज",
      Potato: "आलू",
      Tomato: "टमाटर",
      Wheat: "गेहूँ",
      Soybean: "सोयाबीन",
      Maize: "मक्का",
    },
  },
};

export default translations;