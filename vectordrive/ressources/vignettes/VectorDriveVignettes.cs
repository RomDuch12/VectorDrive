// VectorDrive — vignettes des dessins dans l'explorateur Windows.
// Copyright RomDuch with Claude romduch@gmail.com — MIT OR Apache-2.0.
//
// Fournisseur de vignettes (IThumbnailProvider) chargé par l'explorateur
// (processus isolé « COM Surrogate »). Il ne dessine rien lui-même : il
// demande l'image PNG au serveur de vignettes de VectorDrive par un tube
// nommé (lancé à la première demande, sans fenêtre ; il s'arrête seul au
// bout de deux minutes sans travail). Compilé à la pose par le csc de .NET
// Framework 4 (présent sur tout Windows) : vectordrive/thumbshell.py.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
using Microsoft.Win32;

namespace VectorDrive.Vignettes
{
    [ComImport, Guid("b824b49d-22ac-4161-ac8a-9916e8fa3f7f"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IInitializeWithStream
    {
        void Initialize(IStream pstream, uint grfMode);
    }

    [ComImport, Guid("b7d14566-0509-4cce-a71f-0a554233bd9b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IInitializeWithFile
    {
        void Initialize([MarshalAs(UnmanagedType.LPWStr)] string pszFilePath, uint grfMode);
    }

    [ComImport, Guid("e357fccd-a995-4576-b01f-234630154e96"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IThumbnailProvider
    {
        void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha);
    }

    [ComVisible(true), Guid("6E1C2E8A-3B4F-4C5D-9A7B-0D2E5F6A8B91"), ClassInterface(ClassInterfaceType.None)]
    [ProgId("VectorDrive.Vignettes")]
    public class Fournisseur : IThumbnailProvider, IInitializeWithStream, IInitializeWithFile
    {
        public const string Tube = "vectordrive_vignettes";
        const string Cle = @"Software\VectorDrive\Vignettes";
        const int MaxOctets = 200 * 1024 * 1024;

        string chemin;          // fichier à tracer (copie temporaire pour un flux)
        bool temporaire;

        public void Initialize(string pszFilePath, uint grfMode)
        {
            chemin = pszFilePath;
            temporaire = false;
        }

        public void Initialize(IStream pstream, uint grfMode)
        {
            // le nom du fichier (son extension dit le format), puis son contenu en copie temporaire
            System.Runtime.InteropServices.ComTypes.STATSTG st;
            pstream.Stat(out st, 0);
            string ext = Path.GetExtension(st.pwcsName ?? "").ToLowerInvariant();
            if (ext.Length == 0 || st.cbSize > MaxOctets)
                throw new COMException("format inconnu ou fichier trop grand", unchecked((int)0x80004005));
            string dir = Path.Combine(Path.GetTempPath(), "VectorDrive_vignettes");
            Directory.CreateDirectory(dir);
            string tmp = Path.Combine(dir, Guid.NewGuid().ToString("N") + ext);
            byte[] buf = new byte[1 << 16];
            IntPtr lu = Marshal.AllocCoTaskMem(4);
            try
            {
                using (FileStream f = File.Create(tmp))
                {
                    while (true)
                    {
                        pstream.Read(buf, buf.Length, lu);
                        int n = Marshal.ReadInt32(lu);
                        if (n <= 0) break;
                        f.Write(buf, 0, n);
                    }
                }
            }
            finally
            {
                Marshal.FreeCoTaskMem(lu);
            }
            chemin = tmp;
            temporaire = true;
        }

        public void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha)
        {
            phbmp = IntPtr.Zero;
            pdwAlpha = 0;                                   // WTSAT_UNKNOWN
            try
            {
                byte[] png = Demander(chemin, (int)Math.Max(16, Math.Min(1024, cx)));
                if (png == null || png.Length == 0)
                    throw new COMException("pas de vignette", unchecked((int)0x80004005));
                using (MemoryStream ms = new MemoryStream(png))
                using (Bitmap bmp = new Bitmap(ms))
                {
                    phbmp = bmp.GetHbitmap(Color.White);
                    pdwAlpha = 1;                           // WTSAT_RGB : fond blanc opaque
                }
            }
            finally
            {
                if (temporaire)
                {
                    try { File.Delete(chemin); } catch (Exception) { }
                }
            }
        }

        // Demande au serveur ; le lance s'il ne répond pas (premier appel, ou arrêté faute de travail).
        public static byte[] Demander(string fichier, int taille)
        {
            byte[] req = Encoding.UTF8.GetBytes("VIGNETTE\t" + taille + "\t" + fichier);
            byte[] rep = Echanger(req, 300);
            if (rep != null) return rep;
            Lancer();
            DateTime fin = DateTime.Now.AddSeconds(25);
            while (DateTime.Now < fin)
            {
                rep = Echanger(req, 1000);
                if (rep != null) return rep;
            }
            return null;
        }

        static byte[] Echanger(byte[] req, int attente)
        {
            try
            {
                using (NamedPipeClientStream p = new NamedPipeClientStream(".", Tube, PipeDirection.InOut))
                {
                    p.Connect(attente);
                    p.ReadMode = PipeTransmissionMode.Message;
                    p.Write(req, 0, req.Length);
                    p.Flush();
                    MemoryStream ms = new MemoryStream();
                    byte[] buf = new byte[1 << 16];
                    do
                    {
                        int n = p.Read(buf, 0, buf.Length);
                        if (n <= 0) break;
                        ms.Write(buf, 0, n);
                    } while (!p.IsMessageComplete);
                    return ms.ToArray();
                }
            }
            catch (TimeoutException) { return null; }
            catch (IOException) { return null; }
        }

        static void Lancer()
        {
            string exe = Environment.GetEnvironmentVariable("VECTORDRIVE_VIGNETTES_PROGRAMME");    // essais
            string args = Environment.GetEnvironmentVariable("VECTORDRIVE_VIGNETTES_ARGUMENTS") ?? "";
            if (string.IsNullOrEmpty(exe))
            {
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(Cle))
                {
                    if (k == null) return;
                    exe = k.GetValue("Programme") as string;
                    args = k.GetValue("Arguments") as string ?? "";
                }
            }
            if (string.IsNullOrEmpty(exe) || !File.Exists(exe)) return;
            {
                ProcessStartInfo si = new ProcessStartInfo(exe, args);
                si.UseShellExecute = false;
                si.CreateNoWindow = true;
                si.WindowStyle = ProcessWindowStyle.Hidden;
                try { Process.Start(si); } catch (Exception) { }
            }
        }
    }

    // Essai sans l'explorateur : VectorDriveVignettes.exe fichier taille sortie.png
    public static class Essai
    {
        public static int Main(string[] args)
        {
            if (args.Length < 3) { Console.Error.WriteLine("fichier taille sortie.png"); return 2; }
            Fournisseur f = new Fournisseur();
            ((IInitializeWithFile)f).Initialize(Path.GetFullPath(args[0]), 0);
            IntPtr h; uint a;
            f.GetThumbnail(uint.Parse(args[1]), out h, out a);
            using (Bitmap b = Image.FromHbitmap(h))
                b.Save(args[2], ImageFormat.Png);
            DeleteObject(h);
            Console.WriteLine("ok");
            return 0;
        }

        [DllImport("gdi32.dll")]
        static extern bool DeleteObject(IntPtr h);
    }
}
