import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { StylesProvider } from "@material-ui/core/styles";

import Landing from "./components/Landing";
import Pricing from "./components/Pricing";

const App = () => {
    return (
        <BrowserRouter>
            <StylesProvider>
               <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/pricing" element={<Pricing />} />
                </Routes>
            </StylesProvider>
        </BrowserRouter>
    );
}

export default App;