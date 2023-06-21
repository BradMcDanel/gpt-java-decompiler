import org.junit.Test;
import static org.junit.Assert.*;
import org.evosuite.runtime.EvoRunner;
import org.evosuite.runtime.EvoRunnerParameters;
import org.evosuite.runtime.System;
import org.junit.runner.RunWith;

@RunWith(EvoRunner.class) @EvoRunnerParameters(mockJVMNonDeterminism = true, useVFS = true, useVNET = true, resetStaticState = true, separateClassLoader = true, useJEE = true) 
public class TimeStat_ESTest extends TimeStat_ESTest_scaffolding {

  @Test(timeout = 4000)
  public void test0()  throws Throwable  {
      TimeStat timeStat0 = new TimeStat();
      timeStat0.markStartTime("");
      timeStat0.markEndTime("");
      timeStat0.markStartTime("");
      timeStat0.getTotalMilliseconds("");
      timeStat0.markEndTime("");
      timeStat0.keys();
      String string0 = timeStat0.getAverageSummary();
      assertEquals("Average Summary:\n\n      averaged 0.0 milliseconds. (2 total measurements)\n\n", string0);
      
      timeStat0.markEndTime("");
      timeStat0.markStartTime("");
      double double0 = timeStat0.getTotalMilliseconds("");
      assertEquals(0.0, double0, 1.0E-4);
  }

  @Test(timeout = 4000)
  public void test1()  throws Throwable  {
      System.setCurrentTimeMillis(0L);
      TimeStat timeStat0 = new TimeStat();
      timeStat0.markStartTime("Average Summary:\n\n\n");
      timeStat0.markEndTime("Average Summary:\n\n\n");
      timeStat0.markEndTime("27");
      String string0 = timeStat0.getAverageSummary();
      assertEquals("Average Summary:\n\n     Average Summary:\n\n\n averaged 0.0 milliseconds. (1 total measurements)\n\n", string0);
  }

  @Test(timeout = 4000)
  public void test2()  throws Throwable  {
      TimeStat timeStat0 = new TimeStat();
      timeStat0.markStartTime("");
      timeStat0.markEndTime("");
      timeStat0.getAverageMilliseconds("");
      timeStat0.getAverageSummary();
      timeStat0.markStartTime("");
      timeStat0.getTotalMilliseconds("");
      timeStat0.markEndTime("");
      timeStat0.reset();
      timeStat0.keys();
      timeStat0.getAverageMilliseconds("");
      timeStat0.markEndTime("");
  }

  @Test(timeout = 4000)
  public void test3()  throws Throwable  {
      TimeStat timeStat0 = new TimeStat();
      timeStat0.markStartTime("Average Summary:\n\n\n");
      timeStat0.markEndTime("Average Summary:\n\n\n");
      int int0 = timeStat0.getTotalMeasurements("Average Summary:\n\n\n");
      assertEquals(1, int0);
  }

  @Test(timeout = 4000)
  public void test4()  throws Throwable  {
      TimeStat timeStat0 = new TimeStat();
      double double0 = timeStat0.getTotalMilliseconds("");
      assertEquals(0.0, double0, 1.0E-4);
  }

  @Test(timeout = 4000)
  public void test5()  throws Throwable  {
      TimeStat timeStat0 = new TimeStat();
      int int0 = timeStat0.getTotalMeasurements("Average Summary:\n\n      averaged 0.0 milliseconds. (1 total measurements)\n\n");
      assertEquals(0, int0);
  }
}
