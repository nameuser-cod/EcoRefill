import { useState, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { Capacitor } from "@capacitor/core";
import { ArrowDown, ArrowRight, Check, ChevronRight, Coins, Download, Droplets, History, Home, Leaf, MapPin, QrCode, Recycle, ScanLine, Smartphone, Sparkles, User } from "lucide-react";
import InstallApp from "../../components/InstallApp";
import { ANDROID_DOWNLOAD_URL } from "../../config/appLinks";
import { getInstallSnapshot, subscribeToInstall } from "../../pwa/installPrompt";
import { WATER_OPTIONS } from "../user/constants";
import "../../styles/landing.css";

const previews = [
  { name: "Your points", icon: Coins },
  { name: "Water refills", icon: Droplets },
  { name: "Your activity", icon: History },
];

function Brand() {
  return <span className="landing-brand"><span className="landing-brand-mark"><Recycle size={23} strokeWidth={2.5} aria-hidden="true" /></span><span>Eco<span>Refill</span></span></span>;
}

function AppPreview() {
  const [preview, setPreview] = useState(0);
  const [water, setWater] = useState(WATER_OPTIONS[1]);
  return (
    <div className="landing-product" id="explore">
      <span className="landing-product-orbit" aria-hidden="true" />
      <div className="landing-floating-note landing-note-recycle"><Recycle size={22} aria-hidden="true" /><span>A small habit.<br /><strong>A fresh start.</strong></span></div>
      <div className="landing-phone" aria-label="Interactive example of the EcoRefill app">
        <div className="landing-phone-camera" aria-hidden="true" />
        <div className="landing-phone-top"><Brand /><span className="landing-avatar"><User size={16} aria-hidden="true" /></span></div>
        <div className="landing-phone-greeting"><span>A little good goes a long way.</span><h2>{preview === 0 ? "Hello, recycler!" : preview === 1 ? "Make it a refill." : "Look at you grow."} <Leaf size={20} aria-hidden="true" /></h2></div>
        <div className="landing-balance"><span><Coins size={16} aria-hidden="true" /> Your EcoPoints</span><strong>20.5 <small>pts</small></strong><p>Ready for your next water refill.</p><Recycle size={90} className="landing-balance-art" aria-hidden="true" /></div>
        <div className="landing-phone-content" aria-live="polite">
          {preview === 0 && <><h3>Your next good move</h3><div className="landing-preview-actions"><div><span><ScanLine size={24} /></span><strong>Scan &amp; earn</strong><small>Claim your points</small></div><div><span><MapPin size={24} /></span><strong>Find a machine</strong><small>Plan your next visit</small></div></div><div className="landing-phone-tip"><Droplets size={23} aria-hidden="true" /><p><strong>Points today. Water tomorrow.</strong><br />A 500 mL refill uses 10 EcoPoints.</p><ChevronRight size={17} aria-hidden="true" /></div></>}
          {preview === 1 && <><h3>Pick your next refill</h3><div className="landing-water-options">{WATER_OPTIONS.map((option) => <button type="button" key={option.waterAmountMl} aria-pressed={water.waterAmountMl === option.waterAmountMl} onClick={() => setWater(option)}><Droplets size={21} aria-hidden="true" /><strong>{option.waterAmountMl.toLocaleString()} mL</strong><span>{option.pointsRequired} pts</span></button>)}</div><div className="landing-phone-tip"><Check size={23} aria-hidden="true" /><p><strong>{(20.5 - water.pointsRequired).toFixed(1)} points left after your refill</strong><br />Scan a machine’s refill QR in the app to begin.</p></div></>}
          {preview === 2 && <><h3>Every action adds up</h3><div className="landing-activity"><span><Recycle size={21} aria-hidden="true" /></span><div><strong>Recycling reward</strong><small>Plastic bottles &amp; cans</small></div><b>+5 pts</b></div><div className="landing-activity"><span><Droplets size={21} aria-hidden="true" /></span><div><strong>Water refill</strong><small>500 mL · completed</small></div><b>−10 pts</b></div><p className="landing-preview-caption">Keep your rewards and refills in one place.</p></>}
        </div>
        <div className="landing-phone-nav" aria-hidden="true"><span><Home size={19} />Home</span><span><QrCode size={19} />Scan</span><span><MapPin size={19} />Map</span><span><History size={19} />History</span><span><User size={19} />Profile</span></div>
      </div>
      <div className="landing-floating-note landing-note-water"><span className="landing-note-drop"><Droplets size={24} aria-hidden="true" /></span><span><strong>Less waste.</strong><br />More possibilities.</span></div>
      <div className="landing-preview-switcher" aria-label="Explore the app preview">{previews.map(({ name, icon: Icon }, index) => <button type="button" key={name} onClick={() => setPreview(index)} aria-pressed={preview === index}><Icon size={16} aria-hidden="true" />{name}</button>)}</div>
      <p className="landing-demo-label">Try the preview · Example account and activity</p>
    </div>
  );
}

function Installation() {
  const [platform, setPlatform] = useState(() => /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1) ? "iphone" : "android");
  const { installed } = useSyncExternalStore(subscribeToInstall, getInstallSnapshot);
  const hasApp = installed || Capacitor.isNativePlatform();
  return (
    <section className="landing-install landing-container" id="install" aria-labelledby="install-title">
      <div className="landing-install-intro"><p className="landing-eyebrow"><Smartphone size={16} aria-hidden="true" /> TAKE THE NEXT SMALL STEP</p><h2 id="install-title">Good habits.<br />Now on your home screen.</h2><p>Keep your points, find your next machine, and make every refill count. Start with EcoRefill.</p><div className="landing-install-perks"><span><Check size={17} aria-hidden="true" /> Free to install</span><span><Check size={17} aria-hidden="true" /> Android &amp; iPhone</span></div><p className="landing-connection-note">An internet connection is needed for accounts, rewards, and refills.</p></div>
      <div className="landing-install-card">
        {hasApp ? <><span className="landing-installed-icon"><Check size={32} aria-hidden="true" /></span><h3>You’re ready to EcoRefill.</h3><p>Open your account and start your next good habit.</p><Link className="landing-button landing-button-primary" to="/login">Open EcoRefill <ArrowRight size={18} aria-hidden="true" /></Link></> : <>
          <div className="landing-platforms" aria-label="Choose your phone"><button type="button" onClick={() => setPlatform("android")} aria-pressed={platform === "android"}>Android</button><button type="button" onClick={() => setPlatform("iphone")} aria-pressed={platform === "iphone"}>iPhone / iPad</button></div>
          <div className="landing-install-instructions" aria-live="polite">
            <h3>{platform === "android" ? "Your next refill is a download away." : "Your new home-screen essential."}</h3>
            <ol>{(platform === "android" ? [<>Tap <strong>Download for Android</strong> below.</>, <>Open <strong>EcoRefill.apk</strong> from your downloads. If Android asks, allow this browser to install the app.</>, <>Tap <strong>Install</strong>, open EcoRefill, and create your account.</>] : [<>Open this page in <strong>Safari</strong>.</>, <>Tap <strong>Share</strong>, then <strong>Add to Home Screen</strong>. You may need to scroll down the Share menu.</>, <>Tap <strong>Add</strong>, then open EcoRefill from your home screen and create your account.</>]).map((step, i) => <li key={i}><span>{i + 1}</span><p>{step}</p></li>)}</ol>
            {platform === "android" ? <><a href={ANDROID_DOWNLOAD_URL} className="landing-button landing-button-primary"><Download size={19} aria-hidden="true" /> Download for Android</a><p className="landing-download-note">Android APK · Direct download</p><div className="landing-web-install"><p>Prefer the web app?</p><InstallApp /></div></> : <div className="landing-safari-note"><Smartphone size={19} aria-hidden="true" /><p>Opened this link inside another app? Copy the page link and open it in Safari first.</p></div>}
          </div>
          <p className="landing-browser-option">Want to look around first? <Link to="/register">Get started in your browser <ArrowRight size={14} aria-hidden="true" /></Link></p>
        </>}
      </div>
    </section>
  );
}

export default function DownloadPage() {
  return (
    <div className="landing-page">
      <a className="landing-skip" href="#main">Skip to content</a>
      <header className="landing-header landing-container"><Link to="/download" aria-label="EcoRefill home"><Brand /></Link><nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#explore">Explore the app</a><Link to="/login" className="landing-login">Log in <ArrowRight size={15} aria-hidden="true" /></Link></nav><a href="#install" className="landing-button landing-header-cta">Get the app <ArrowDown size={15} aria-hidden="true" /></a></header>
      <main id="main">
        <section className="landing-hero landing-container" aria-labelledby="hero-title"><div className="landing-hero-copy"><p className="landing-eyebrow"><span className="landing-live-dot" /> SMALL ACTIONS. REAL REWARDS.</p><h1 id="hero-title">Your empty bottle.<br />Your next <span>refill.</span></h1><p className="landing-hero-description">Give bottles and cans a fresh purpose. Recycle with EcoRefill, earn EcoPoints, and turn them into water refills.</p><div className="landing-hero-actions"><a href="#install" className="landing-button landing-button-primary">Get EcoRefill <ArrowRight size={19} aria-hidden="true" /></a><a href="#how-it-works" className="landing-text-link">See how it works <ArrowDown size={17} aria-hidden="true" /></a></div><div className="landing-hero-caption"><span><Leaf size={17} aria-hidden="true" /></span><p>A little less waste.<br /><strong>A little more possibility.</strong></p></div></div><AppPreview /></section>
        <div className="landing-cycle-strip"><div className="landing-container"><span><Recycle size={23} aria-hidden="true" /> Recycle a little.</span><span className="landing-strip-arrow" aria-hidden="true">↗</span><span><Coins size={23} aria-hidden="true" /> Earn something good.</span><span className="landing-strip-arrow" aria-hidden="true">↗</span><span><Droplets size={23} aria-hidden="true" /> Refill. Repeat.</span></div></div>
        <section className="landing-how landing-container" id="how-it-works" aria-labelledby="how-title"><div className="landing-section-heading"><div><p className="landing-eyebrow">ONE SIMPLE CYCLE</p><h2 id="how-title">From empty to possibility.</h2></div><p>No complicated routine. Just your everyday recyclables, doing a little more good.</p></div><div className="landing-steps"><article><div className="landing-step-heading"><span className="landing-step-icon"><Recycle size={30} aria-hidden="true" /></span><span className="landing-step-number">01</span></div><h3>Give it another life.</h3><p>Bring clean, empty plastic bottles or aluminum cans to an EcoRefill machine. Insert them one at a time.</p><span className="landing-step-label">RECYCLE</span></article><article><div className="landing-step-heading"><span className="landing-step-icon"><ScanLine size={30} aria-hidden="true" /></span><span className="landing-step-number">02</span></div><h3>Make every item count.</h3><p>Finish your batch with the green button. Scan the machine’s reward QR inside the app to collect your EcoPoints.</p><span className="landing-step-label">EARN</span></article><article><div className="landing-step-heading"><span className="landing-step-icon"><Droplets size={30} aria-hidden="true" /></span><span className="landing-step-number">03</span></div><h3>Come back for a refill.</h3><p>Bring your water container. Scan the machine’s refill QR, choose your water amount, and use your saved points.</p><span className="landing-step-label">REFILL</span></article></div></section>
        <section className="landing-features landing-container" aria-labelledby="features-title"><div className="landing-feature-heading"><Sparkles size={25} aria-hidden="true" /><h2 id="features-title">A pocket-sized<br />reason to keep going.</h2><p>More than a balance. A home for your next good habit.</p></div><div className="landing-feature-list"><div><Coins size={24} aria-hidden="true" /><div><h3>Your points, always in view.</h3><p>See your EcoPoints balance and know when you’re ready for your next refill.</p></div></div><div><MapPin size={24} aria-hidden="true" /><div><h3>Find your next stop.</h3><p>Find EcoRefill machines on the map and open directions for your next visit.</p></div></div><div><History size={24} aria-hidden="true" /><div><h3>See the good add up.</h3><p>Follow your recycling rewards and water refills in your transaction history.</p></div></div></div></section>
        <Installation />
        <section className="landing-faq landing-container" aria-labelledby="faq-title"><h2 id="faq-title">A few things to know.</h2><div><details><summary>What can I recycle?<ChevronRight size={18} aria-hidden="true" /></summary><p>EcoRefill accepts supported clean, empty plastic bottles and aluminum cans. Insert one at a time. The machine checks each item before awarding points; rejected items do not earn points.</p></details><details><summary>How many points do I need for a refill?<ChevronRight size={18} aria-hidden="true" /></summary><p>Choose 250 mL for 5 EcoPoints, 500 mL for 10 EcoPoints, or 1,000 mL for 15 EcoPoints. Bring a suitable container and place it at the outlet before confirming your refill in the app.</p></details><details><summary>Do I need to install the app?<ChevronRight size={18} aria-hidden="true" /></summary><p>You can use EcoRefill in your browser, too. Create an account to collect recycling rewards and use your points. Installation gives you a convenient home-screen shortcut. Machine alert push notifications for owners are available in the Android app.</p></details><details><summary>Is this QR code for claiming points?<ChevronRight size={18} aria-hidden="true" /></summary><p>This QR opens the EcoRefill introduction and installation page. To claim points, sign in and use the app’s scanner on the reward QR displayed by the machine after recycling.</p></details></div></section>
      </main>
      <footer className="landing-footer landing-container"><Brand /><p>Recycle. Refill. Repeat.</p><Link to="/login">Open EcoRefill <ArrowRight size={15} aria-hidden="true" /></Link></footer>
    </div>
  );
}
