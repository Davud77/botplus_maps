import React from 'react';
import '../SetupPage.css';
export default function AuthLayout({ children, title }: React.PropsWithChildren<{ title: string }>) {
  return <main className="setup-shell"><aside className="setup-intro">
    <a className="setup-brand" href="/"><span className="setup-brand-icon">B+</span>BotPlus Maps</a>
    <div className="setup-intro-copy"><span className="setup-eyebrow">ВАША ГЕОПЛАТФОРМА</span>
      <h1>Ваши карты.<br />Ваши данные.<br /><em>Ваши правила.</em></h1>
      <p>Собственное пространство для ортофотопланов, панорам и векторных слоёв. На вашей инфраструктуре.</p>
      <div className="setup-terrain" aria-hidden="true"><i /><i /><i /><i /><b>+ 42.97° N · 47.50° E</b></div>
    </div><footer>SELF-HOSTED GIS <span>Открытый код · AGPL-3.0</span></footer>
  </aside><section className="setup-panel" aria-label={title}>{children}<footer className="setup-panel-footer">Данные остаются под вашим контролем.</footer></section></main>;
}
