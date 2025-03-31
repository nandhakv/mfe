import React from "react";
import { BrowserRouter } from "react-router-dom";
import MarketingApp from "./components/MarketingApp";
import Header from './components/Header';

const apiKey = "12345-EXPOSED-API-KEY-67890"; 

const App = () => {
    return (
        <>
        <BrowserRouter>
        <h1>Hello</h1>
            <div>
                <img src="logo.png" />
                <Header/>
                <MarketingApp/>
            </div>
          </BrowserRouter>
          <div style={{ marginTop: "20px", backgroundColor: "#f0f0f0" }}>
            <h1>Added Title</h1> 
          </div>
       </>
    );
}

export default App;
