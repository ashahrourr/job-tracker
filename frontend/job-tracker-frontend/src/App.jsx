import { useState, useEffect } from "react";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBriefcase } from "@fortawesome/free-solid-svg-icons";

const API_URL = import.meta.env.VITE_BACKEND_URL;

function App() {
  const [jobs, setJobs] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [token, setToken] = useState(localStorage.getItem("jwt") || null);

  // ✅ Extract token from URL if redirected after Google login
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const jwtFromUrl = urlParams.get("token");

    if (jwtFromUrl) {
      localStorage.setItem("jwt", jwtFromUrl);
      setToken(jwtFromUrl);
      // ✅ Remove token from URL after storing it
      window.history.replaceState({}, document.title, "/");
    }
  }, []);

  // ✅ Function to Log In via Google OAuth
  const handleLogin = async () => {
    window.location.href = `${API_URL}/auth/login`;
  };

  // ✅ Function to Log Out
  const handleLogout = () => {
    localStorage.removeItem("jwt");
    setToken(null);
    setJobs([]);
  };

  // ✅ Fetch Job Applications for the Logged-in User
  useEffect(() => {
    if (token) {
      axios
        .get(`${API_URL}/jobs/`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        .then((response) => setJobs(response.data))
        .catch((error) => console.error("Error fetching jobs:", error));
    }
  }, [token]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-gray-100">
      <header className="px-4 py-8 bg-gray-900/80 backdrop-blur-sm border-b border-gray-700">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent mb-8">
            Job Application Tracker
          </h1>

          {/* ✅ Display Login/Logout Button */}
          {token ? (
            <button
              onClick={handleLogout}
              className="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded transition-all"
            >
              Logout
            </button>
          ) : (
            <button
              onClick={handleLogin}
              className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition-all"
            >
              Login with Google
            </button>
          )}

          {/* ✅ Stats Section */}
          <div className="flex flex-wrap gap-4 mt-4">
            <div className="flex-1 min-w-[200px] bg-gray-800/50 p-4 rounded-xl border border-gray-700">
              <div className="text-2xl font-bold text-purple-400">{jobs.length}</div>
              <div className="text-sm text-gray-400">Total Applications</div>
            </div>
            <div className="flex-1 min-w-[200px] bg-gray-800/50 p-4 rounded-xl border border-gray-700">
              <div className="text-2xl font-bold text-green-400">
                {jobs.filter(job => job.status === 'interview').length}
              </div>
              <div className="text-sm text-gray-400">Interviews</div>
            </div>
          </div>
        </div>
      </header>

      {/* ✅ Job Listings */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-8">
          <input
            type="text"
            placeholder="Search jobs..."
            className="w-full p-4 bg-gray-800/50 rounded-lg border border-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {jobs.length === 0 ? (
            <div className="col-span-full text-center py-12 text-gray-400">
              <FontAwesomeIcon icon={faBriefcase} className="text-4xl mb-4" />
              <p>No job applications found</p>
            </div>
          ) : (
            jobs.map((job) => (
              <div 
                key={job.id}
                className="bg-gray-800/50 rounded-xl p-4 border border-gray-700 hover:border-purple-500 transition-all"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-semibold text-purple-400">{job.company}</h3>
                  <span className="text-sm text-gray-400">
                    {new Date(job.applied_date).toLocaleDateString()}
                  </span>
                </div>
                <h4 className="text-gray-200 font-medium mb-4">{job.job_title}</h4>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs px-3 py-1 bg-gray-500 text-white rounded-full">
                    {job.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
