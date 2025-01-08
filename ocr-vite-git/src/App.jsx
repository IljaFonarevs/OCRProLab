// import { useState } from 'react'
import './App.css'
// import { Tab } from "primitives"

function App() {

  return (
    <>
    <div id='content'>
      <header>
        <img id='logo' src="/src/images/logo.png" alt='logo' />
        <div id='gray-buttons'>
          <div className='gray-button'>
            <div className='gray-button-text'>Sign Up</div>
          </div>
          <div className='gray-button'>
            <div className='gray-button-text'>Log in</div>
          </div>
        </div>
      </header>
      <div id='main-field'>
        <div id='red-button'>
          <div id='red-button-text'>Create CO2 Report</div>
        </div>
        <div id='explain-text'>Press the button to find out what is your CO2 emission</div>
        
      </div>
      {/* <Tab id="3.grupa">3.grupa</Tab> */}
      <footer><div id='footer-text'>© RTU</div></footer>
    </div>
    </>
  )
}

export default App
