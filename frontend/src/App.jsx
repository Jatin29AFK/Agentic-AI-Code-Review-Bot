import { Navigate, Route, Routes } from "react-router-dom";
import Footer from "./components/Footer";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import NewReview from "./pages/NewReview";
import ReviewHistory from "./pages/ReviewHistory";
import ReviewResult from "./pages/ReviewResult";

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <Navbar />
      <main className="flex w-full flex-1 flex-col px-4 pb-24 pt-8 sm:px-6 lg:px-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/reviews/new" element={<NewReview />} />
          <Route path="/reviews/:reviewId" element={<ReviewResult />} />
          <Route path="/history" element={<ReviewHistory />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
