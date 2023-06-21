import java.sql.*;
import java.util.*;

public class TimeStat {
  /** Hash that holds a single start time for any single key */
  private Hashtable starts = new Hashtable();

  /** Hash that holds all the measurement (duration) times for any single key */
  private Hashtable times = new Hashtable();

  /** Sole constructor */
  public TimeStat() {
    reset();
  }

  /** Resets all measurements by deleting all times. */
  public void reset() {
    starts = new Hashtable();
    times = new Hashtable();
  }

  /**
   * Marks the start time for a given measurement, identified by a key. Any previous start time in
   * the hash is overwritten.
   */
  public void markStartTime(String key) {
    starts.put(key, new Timestamp((new java.util.Date()).getTime()));
  }

  /**
   * Marks the end time for a given measurement, identified by a key. This method enters a new
   * measurement, and deletes the reference in the start time hash. If there is no corresponding
   * start time, nothing happens.
   */
  public void markEndTime(String key) {
    Timestamp end = new Timestamp((new java.util.Date()).getTime());
    Timestamp start = (Timestamp) starts.get(key);
    if (start != null) {
      starts.remove(key);
      long endMs = end.getTime();
      long startMs = start.getTime();
      long diff = endMs - startMs;
      ArrayList all = (ArrayList) times.get(key);
      if (all == null) {
        all = new ArrayList();
        times.put(key, all);
      }
      all.add(new Long(diff));
    }
  }

  /** Returns a summary of all keys, and their timed averages. */
  public String getAverageSummary() {
    StringBuffer sb = new StringBuffer("Average Summary:\n\n");
    for (Enumeration e = times.keys(); e.hasMoreElements(); ) {
      String key = (String) e.nextElement();
      double avgmSec = getAverageMilliseconds(key);
      sb.append(
          "     "
              + key
              + " averaged "
              + avgmSec
              + " milliseconds. ("
              + getTotalMeasurements(key)
              + " total measurements)\n");
    }
    sb.append("\n");
    return sb.toString();
  }

  /** Returns an Enumeration of all keys used for measurements. */
  public Enumeration keys() {
    return times.keys();
  }

  /** Returns the total number of measurements for a given key. */
  public int getTotalMeasurements(String key) {
    ArrayList all = (ArrayList) times.get(key);
    if (all != null) {
      return all.size();
    }
    return 0;
  }

  /**
   * Returns the average number of milliseconds for all start/end measurements for the provided key
   */
  public double getAverageMilliseconds(String key) {
    ArrayList all = (ArrayList) times.get(key);
    if (all != null) {
      long total = 0;
      for (Iterator i = all.iterator(); i.hasNext(); ) {
        Long msec = (Long) i.next();
        total += msec.longValue();
      }
      return ((double) total / (double) all.size());
    }
    return 0.0;
  }

  /**
   * Returns the total number of milliseconds for all start/end measurements for the provided key
   */
  public double getTotalMilliseconds(String key) {
    ArrayList all = (ArrayList) times.get(key);
    if (all != null) {
      long total = 0;
      for (Iterator i = all.iterator(); i.hasNext(); ) {
        Long msec = (Long) i.next();
        total += msec.longValue();
      }
      return (double) total;
    }
    return 0.0;
  }
}
