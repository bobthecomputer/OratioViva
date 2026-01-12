import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const sampleVoices = {
  voices: [
    { id: "kokoro_en_us_0", label: "Kokoro US Neutral", language: "en" },
    { id: "parler_en_neutral", label: "Parler Neutral", language: "en" },
  ],
};

const sampleHistory = {
  items: [
    {
      job_id: "job-1",
      text_preview: "Hello world",
      model: "kokoro",
      voice_id: "kokoro_en_us_0",
      source: "stub",
      created_at: new Date().toISOString(),
      audio_url: "/audio/job-1.wav",
    },
  ],
};

const sampleJobs = {
  items: [
    {
      job_id: "job-1",
      status: "succeeded",
      voice_id: "kokoro_en_us_0",
      model: "kokoro",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
};

function createFetchMock() {
  const fetchMock = vi.fn(async (url, opts = {}) => {
    if (url.includes("/voices")) {
      return { ok: true, json: async () => sampleVoices };
    }
    if (url.includes("/models/status")) {
      return {
        ok: true,
        json: async () => ({
          models: [],
          needs_download: false,
          downloading: false,
          provider: "stub",
        }),
      };
    }
    if (url.includes("/models/download")) {
      return { ok: true, json: async () => ({ status: "started" }) };
    }
    if (url.includes("/history")) {
      if (opts.method === "DELETE") {
        return { ok: true, json: async () => ({ status: "ok" }) };
      }
      return { ok: true, json: async () => sampleHistory };
    }
    if (url.includes("/jobs/batch_delete") || url.includes("/history/batch_delete")) {
      return { ok: true, json: async () => ({ status: "ok" }) };
    }
    if (url.includes("/jobs/") && opts.method === "DELETE") {
      return { ok: true, json: async () => ({ status: "ok" }) };
    }
    if (url.includes("/jobs")) {
      return { ok: true, json: async () => sampleJobs };
    }
    if (url.includes("/export/zip")) {
      return { ok: true, blob: async () => new Blob(["fakezip"], { type: "application/zip" }) };
    }
    if (url.includes("/synthesize")) {
      return {
        ok: true,
        json: async () => ({ job_id: "job-1", status: "queued" }),
      };
    }
    return { ok: false, text: async () => "not found", status: 404 };
  });
  global.fetch = fetchMock;
  return fetchMock;
}

describe("App selection and export", () => {
  beforeEach(() => {
    createFetchMock();
  });

  it("allows selecting history items and triggering export", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Hello world/)).toBeInTheDocument();
    });

    const checkbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(checkbox);

    const exportBtn = screen.getByText(/Export ZIP/);
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/export/zip"), expect.any(Object));
    });
  });

  it("allows batch delete of jobs", async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/File d'attente/));
    const checkboxes = screen.getAllByRole("checkbox");
    const checkbox = checkboxes[checkboxes.length - 1]; // take one from jobs list
    fireEvent.click(checkbox);
    const deleteButtons = screen.getAllByText(/Supprimer selection/);
    const jobsDeleteBtn = deleteButtons[deleteButtons.length - 1];
    fireEvent.click(jobsDeleteBtn);
    await waitFor(() => {
      const called = global.fetch.mock.calls.some(
        ([url]) => typeof url === "string" && url.includes("/jobs/batch_delete"),
      );
      expect(called).toBe(true);
    });
  });
});
