import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from 'sonner';
import { UnreadMessagesProvider, useUnreadMessages } from './context/UnreadMessagesContext';
import { GlobalUnreadBanner } from './components/GlobalUnreadBanner';
import DirectMessageAlert from './components/DirectMessageAlert';
import Auth from './pages/Auth';
import ResetPassword from './pages/ResetPassword';
import VerifyEmail from './pages/VerifyEmail';
import Login from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Clients } from './pages/Clients';
import { InitialContacts } from './pages/InitialContacts';
import { InventoryAccountingReport } from './pages/InventoryAccountingReport';
import { AssetLedgerReport } from './pages/AssetLedgerReport';
import InvoicedExitsReport from './pages/InvoicedExitsReport';
import { ClientTemplatesConfig } from './pages/ClientTemplatesConfig';
import { EmailFooterConfig } from './pages/EmailFooterConfig';
import { EmailSendersConfig } from './pages/EmailSendersConfig';
import { WorkCalendarConfig } from './pages/WorkCalendarConfig';
import { CommercialCategories } from './pages/CommercialCategories';
import { NotificationConfig } from './pages/NotificationConfig';
import ActionNotificationsConfig from './pages/ActionNotificationsConfig';
import OtherActionsConfig from './pages/OtherActionsConfig';
import ProjectSlaConfig from './pages/ProjectSlaConfig';
import ConnectedUsers from './pages/ConnectedUsers';
import BackupCenter from './pages/BackupCenter';
import { IntegratorTemplatesConfig, NewProductTemplatesConfig } from './pages/EntityTemplatesConfig';
import HistoricalQuotes from './pages/HistoricalQuotes';
import SalesReports from './pages/SalesReports';
import SponsorReports from './pages/SponsorReports';
import Banks from './pages/Banks';
import BankDetail from './pages/BankDetail';
import IntegrationReport from './pages/IntegrationReport';
import Hardware from './pages/Hardware';
import MediosPago from './pages/MediosPago';
import Integrators from './pages/Integrators';
import Quotes from './pages/Quotes';
import ExchangeRate from './pages/ExchangeRate';
import Settings from './pages/Settings';
import AdminUsers from './pages/AdminUsers';
import AdminProfiles from './pages/AdminProfiles';
import UserManagement from './pages/UserManagement';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import DirectProjectCreation from './pages/DirectProjectCreation';
import DatosImple from './pages/DatosImple';
import BankPaymentConditions from './pages/BankPaymentConditions';
import NewProducts from './pages/NewProducts';
import Inventory from './pages/Inventory';
import TallerEquipos from './pages/TallerEquipos';
import AuthCallback from './components/AuthCallback';
import ProtectedRoute from './components/ProtectedRoute';

function AppRouter() {
  const location = useLocation();
  
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/login-google" element={<Login />} />
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      } />
      <Route path="/clients" element={
        <ProtectedRoute>
          <Clients />
        </ProtectedRoute>
      } />
      <Route path="/initial-contacts" element={
        <ProtectedRoute>
          <InitialContacts />
        </ProtectedRoute>
      } />
      <Route path="/banks" element={
        <ProtectedRoute>
          <Banks />
        </ProtectedRoute>
      } />
      <Route path="/banks/integrations/report" element={
        <ProtectedRoute>
          <IntegrationReport />
        </ProtectedRoute>
      } />
      <Route path="/banks/:bankId" element={
        <ProtectedRoute>
          <BankDetail />
        </ProtectedRoute>
      } />
      <Route path="/hardware" element={
        <ProtectedRoute>
          <Hardware />
        </ProtectedRoute>
      } />
      <Route path="/medios-pago" element={
        <ProtectedRoute>
          <MediosPago />
        </ProtectedRoute>
      } />
      <Route path="/integrators" element={
        <ProtectedRoute>
          <Integrators />
        </ProtectedRoute>
      } />
      <Route path="/quotes" element={
        <ProtectedRoute>
          <Quotes />
        </ProtectedRoute>
      } />
      <Route path="/projects" element={
        <ProtectedRoute>
          <Projects />
        </ProtectedRoute>
      } />
      <Route path="/direct-projects" element={
        <ProtectedRoute>
          <DirectProjectCreation />
        </ProtectedRoute>
      } />
      <Route path="/datos-imple" element={
        <ProtectedRoute>
          <DatosImple />
        </ProtectedRoute>
      } />
      <Route path="/condiciones-banco-mediopago" element={
        <ProtectedRoute>
          <BankPaymentConditions />
        </ProtectedRoute>
      } />
      <Route path="/projects/:projectId" element={
        <ProtectedRoute>
          <ProjectDetail />
        </ProtectedRoute>
      } />
      <Route path="/new-products" element={
        <ProtectedRoute>
          <NewProducts />
        </ProtectedRoute>
      } />
      <Route path="/inventory" element={
        <ProtectedRoute>
          <Inventory />
        </ProtectedRoute>
      } />
      <Route path="/inventory/accounting-report" element={
        <ProtectedRoute>
          <InventoryAccountingReport />
        </ProtectedRoute>
      } />
      <Route path="/inventory/asset-ledger" element={
        <ProtectedRoute>
          <AssetLedgerReport />
        </ProtectedRoute>
      } />
      <Route path="/inventory/invoiced-exits" element={
        <ProtectedRoute>
          <InvoicedExitsReport />
        </ProtectedRoute>
      } />
      <Route path="/clients/communications" element={
        <ProtectedRoute>
          <ClientTemplatesConfig />
        </ProtectedRoute>
      } />
      <Route path="/integrators/communications" element={
        <ProtectedRoute>
          <IntegratorTemplatesConfig />
        </ProtectedRoute>
      } />
      <Route path="/new-products/communications" element={
        <ProtectedRoute>
          <NewProductTemplatesConfig />
        </ProtectedRoute>
      } />
      <Route path="/historical-quotes" element={
        <ProtectedRoute>
          <HistoricalQuotes />
        </ProtectedRoute>
      } />
      <Route path="/reports/sales" element={
        <ProtectedRoute>
          <SalesReports />
        </ProtectedRoute>
      } />
      <Route path="/reports/sponsors" element={
        <ProtectedRoute>
          <SponsorReports />
        </ProtectedRoute>
      } />
      <Route path="/taller-equipos" element={
        <ProtectedRoute>
          <TallerEquipos />
        </ProtectedRoute>
      } />
      <Route path="/exchange-rate" element={
        <ProtectedRoute>
          <ExchangeRate />
        </ProtectedRoute>
      } />
      <Route path="/settings" element={
        <ProtectedRoute>
          <Settings />
        </ProtectedRoute>
      } />
      <Route path="/settings/email-footer" element={
        <ProtectedRoute>
          <EmailFooterConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/email-senders" element={
        <ProtectedRoute>
          <EmailSendersConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/work-calendar" element={
        <ProtectedRoute>
          <WorkCalendarConfig />
        </ProtectedRoute>
      } />
      <Route path="/commercial-categories" element={
        <ProtectedRoute>
          <CommercialCategories />
        </ProtectedRoute>
      } />
      <Route path="/settings/notifications" element={
        <ProtectedRoute>
          <NotificationConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/action-notifications" element={
        <ProtectedRoute>
          <ActionNotificationsConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/other-actions" element={
        <ProtectedRoute>
          <OtherActionsConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/project-sla" element={
        <ProtectedRoute>
          <ProjectSlaConfig />
        </ProtectedRoute>
      } />
      <Route path="/settings/connected-users" element={
        <ProtectedRoute>
          <ConnectedUsers />
        </ProtectedRoute>
      } />
      <Route path="/settings/backup-center" element={
        <ProtectedRoute>
          <BackupCenter />
        </ProtectedRoute>
      } />
      <Route path="/admin/users" element={
        <ProtectedRoute>
          <AdminUsers />
        </ProtectedRoute>
      } />
      <Route path="/admin/profiles" element={
        <ProtectedRoute>
          <AdminProfiles />
        </ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute>
          <UserManagement />
        </ProtectedRoute>
      } />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function AppToaster() {
  // Cuando el banner global está visible, empuja los toasts hacia abajo para
  // que no se solapen con la caja roja fija de la esquina superior derecha.
  const { unread } = useUnreadMessages();
  return <Toaster position="top-right" richColors offset={unread > 0 ? { top: 96 } : undefined} />;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <UnreadMessagesProvider>
          <AppRouter />
          <GlobalUnreadBanner />
          <DirectMessageAlert />
          <AppToaster />
        </UnreadMessagesProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
