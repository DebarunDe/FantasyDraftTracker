import { BrowserRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { DraftBoard } from './components/draft/DraftBoard';
import { LandingPage } from './components/lobby/LandingPage';
import { SetupWizard } from './components/setup/SetupWizard';
import './styles/globals.css';
import './styles/positions.css';
import './styles/animations.css';
import './styles/mobile.css';

function HomeRoute() {
  const navigate = useNavigate();
  return <LandingPage onNewDraft={() => navigate('/new')} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomeRoute />} />
        <Route path="/new" element={<SetupWizard />} />
        <Route path="/draft/:draftId" element={<DraftBoard />} />
      </Routes>
    </BrowserRouter>
  );
}
