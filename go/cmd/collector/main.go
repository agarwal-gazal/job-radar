package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"golang.org/x/time/rate"

	// Replace YOURNAME to match your go.mod module line.
	"github.com/agarwal-gazal/job-radar/go/internal/boards"
)

type target struct {
	source string // "greenhouse" or "lever"
	name   string // board token or site name
}

func main() {
	inPath := flag.String("boards", "boards.txt", "file of 'source,name' lines")
	outPath := flag.String("out", "../data/jobs.jsonl", "where to write results")
	workers := flag.Int("workers", 8, "how many boards to fetch at once")
	rps := flag.Float64("rps", 2, "requests per second, across all workers")
	flag.Parse()

	targets, err := readTargets(*inPath)
	if err != nil {
		log.Fatalf("reading %s: %v", *inPath, err)
	}
	log.Printf("%d boards to fetch", len(targets))

	// Politeness. rate.NewLimiter(r, b) allows r events per second
	// with a burst of b. A burst of 1 means strictly paced.
	limiter := rate.NewLimiter(rate.Limit(*rps), 1)

	// One shared client, so connections are reused between fetches.
	client := &http.Client{Timeout: 20 * time.Second}

	work := make(chan target)
	results := make(chan boards.Job)

	// --- start the workers ---
	var wg sync.WaitGroup
	for i := 0; i < *workers; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			// Reading from a channel with range keeps going until
			// the channel is closed. That is how a worker knows
			// there is no more work.
			for t := range work {
				ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)

				// Block here until the rate limiter allows a call.
				if err := limiter.Wait(ctx); err != nil {
					cancel()
					continue
				}

				jobs, err := fetch(ctx, client, t)
				cancel()
				if err != nil {
					// One bad board must never stop the run.
					log.Printf("worker %d: skip %s/%s: %v", id, t.source, t.name, err)
					continue
				}
				for _, j := range jobs {
					results <- j
				}
			}
		}(i)
	}

	// --- feed the workers, then say there is no more ---
	go func() {
		for _, t := range targets {
			work <- t
		}
		close(work)
	}()

	// --- when every worker is done, close results ---
	go func() {
		wg.Wait()
		close(results)
	}()

	// --- collect, dedupe, write ---
	f, err := os.Create(*outPath)
	if err != nil {
		log.Fatalf("creating %s: %v", *outPath, err)
	}
	defer f.Close()

	enc := json.NewEncoder(f)
	seen := make(map[string]bool)
	kept, dupes := 0, 0

	// This loop ends when results is closed and drained.
	for j := range results {
		if seen[j.Hash] {
			dupes++
			continue
		}
		seen[j.Hash] = true
		if err := enc.Encode(j); err != nil {
			log.Fatalf("writing: %v", err)
		}
		kept++
	}

	log.Printf("wrote %d jobs to %s, skipped %d duplicates", kept, *outPath, dupes)
}

func fetch(ctx context.Context, c *http.Client, t target) ([]boards.Job, error) {
	switch t.source {
	case "greenhouse":
		return boards.FetchGreenhouse(ctx, c, t.name)
	case "lever":
		return boards.FetchLever(ctx, c, t.name)
	default:
		return nil, fmt.Errorf("unknown source %q", t.source)
	}
}

func readTargets(path string) ([]target, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var out []target
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, ",", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("bad line %q, want 'source,name'", line)
		}
		out = append(out, target{
			source: strings.TrimSpace(parts[0]),
			name:   strings.TrimSpace(parts[1]),
		})
	}
	return out, sc.Err()
}
