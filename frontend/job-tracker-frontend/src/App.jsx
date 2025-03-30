import { useState, useEffect } from "react";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBriefcase, faSignOutAlt } from "@fortawesome/free-solid-svg-icons";

const API_URL = import.meta.env.VITE_BACKEND_URL;

function toTitleCase(text) {
  return text.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function App() {
  const [jobs, setJobs] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [token, setToken] = useState(localStorage.getItem("jwt") || null);

    // Add filtered jobs state
    const [filteredJobs, setFilteredJobs] = useState([]);

    // Add search filtering effect
    useEffect(() => {
      const filtered = jobs.filter(job => 
        job.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.job_title.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredJobs(filtered);
    }, [searchTerm, jobs]);


  // ========== 3) Setup Axios Interceptor for fallback on 401 ==========
  const setupAxios = () => {
    axios.interceptors.response.use(
      (res) => res,
      async (err) => {
        const original = err.config;
        if (err.response?.status === 401 && !original._retry) {
          original._retry = true;
  
          // Clear token and redirect to login
          localStorage.removeItem("jwt");
          setToken(null);
          window.location.href = `${API_URL}/auth/login`;
          return Promise.reject(err);
        }
  
        return Promise.reject(err);
      }
    );
  };
  

  // ========== 4) On mount, check if we got ?token= in URL ==========
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const jwtFromUrl = urlParams.get("token");

    if (jwtFromUrl) {
      localStorage.setItem("jwt", jwtFromUrl);
      setToken(jwtFromUrl);
      // Remove token from the URL so we don't repeatedly parse it
      window.history.replaceState({}, document.title, "/");
    }
  }, []);

  // ========== 6) handle login/logout ==========
  const handleLogin = () => {
    window.location.href = `${API_URL}/auth/login`;
  };

  const handleLogout = () => {
    localStorage.removeItem("jwt");
    setToken(null);
    setJobs([]);
  };

  // ========== 7) handleDelete job example ==========
  const handleDelete = async (jobId) => {
    try {
      await axios.delete(`${API_URL}/jobs/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setJobs(jobs.filter((job) => job.id !== jobId));
    } catch (error) {
      console.error("Error deleting job:", error);
    }
  };

  // ========== 8) Fetch jobs whenever token changes ==========
  useEffect(() => {
    setupAxios();
  
    const urlParams = new URLSearchParams(window.location.search);
    const jwtFromUrl = urlParams.get("token");
  
    if (jwtFromUrl) {
      localStorage.setItem("jwt", jwtFromUrl);
      setToken(jwtFromUrl);
      window.history.replaceState({}, document.title, "/");
    }
  
    const fetchJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/jobs/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setJobs(response.data);
      } catch (error) {
        console.error("Error fetching jobs:", error);
      }
    };
  
    if (token) {
      fetchJobs();
    }
  }, [token]);
  

  // ========== 9) Return your UI ==========
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-gray-100">
      <header className="px-4 py-8 bg-gray-900/80 backdrop-blur-sm border-b border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="flex justify-between items-start mb-8">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              Job Application Tracker
            </h1>
            
            {token ? (
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 bg-red-600/80 hover:bg-red-700/90 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 shadow-lg hover:shadow-red-500/20"
              >
                <FontAwesomeIcon icon={faSignOutAlt} className="w-4 h-4" />
                Logout
              </button>
            ) : (
              <button
                onClick={handleLogin}
                className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-all duration-200"
              >
                Login with Google
              </button>
            )}
          </div>

          {/* Simplified Stats Section */}
          <div className="flex flex-wrap gap-4 mt-4">
            <div className="flex-1 min-w-[200px] bg-gray-800/50 p-4 rounded-xl border border-gray-700">
              <div className="text-2xl font-bold text-purple-400">{jobs.length}</div>
              <div className="text-sm text-gray-400">Total Applications</div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-8">
          <input
            type="text"
            placeholder="Search jobs..."
            className="w-full p-4 bg-gray-800/50 rounded-lg border border-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder-gray-400"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredJobs.length === 0 ? (
            <div className="col-span-full text-center py-12 text-gray-400">
              <FontAwesomeIcon icon={faBriefcase} className="text-4xl mb-4" />
              <p>{jobs.length === 0 ? 'No job applications found' : 'No matching results'}</p>
            </div>
          ) : (
            filteredJobs.map((job) => (
              <div
                key={job.id}
                className="relative group bg-gray-800/50 rounded-xl p-4 border border-gray-700 hover:border-purple-500 transition-all"
              >
                <button
                  onClick={() => handleDelete(job.id)}
                  className="absolute -top-1.5 -right-1.5 bg-red-500/90 opacity-0 group-hover:opacity-100 text-white rounded-md w-5 h-5 flex items-center justify-center transition-all duration-200 shadow-lg hover:bg-red-600 text-xs"
                  title="Delete this entry"
                >
                  <span className="relative top-[-0.5px]">×</span>
                </button>

                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-semibold text-purple-400">
                    {toTitleCase(job.company)}
                  </h3>
                  <span className="text-sm text-gray-400">
                    {new Date(job.applied_date).toLocaleDateString()}
                  </span>
                </div>
                <h4 className="text-gray-200 font-medium mb-4">
                  {toTitleCase(job.job_title)}
                </h4>
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
