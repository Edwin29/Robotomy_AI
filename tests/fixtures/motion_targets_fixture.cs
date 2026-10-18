// Runs the production candidate adapter against a minimal hierarchy API. This is
// a selection/ownership regression, not a Unity render or gameplay acceptance test.
using System;
using System.Collections.Generic;
using UnityEngine;
namespace UnityEngine {
    public class Object { }
    public class Component : Object {
        public GameObject gameObject;
        public Transform transform { get { return gameObject.transform; } }
        public T[] GetComponents<T>() where T:Component { return gameObject.GetComponents<T>(); }
        public T GetComponentInParent<T>() where T:Component {
            for(Transform p=transform;p!=null;p=p.parent) {
                T[] found=p.GetComponents<T>(); if(found.Length>0) return found[0];
            }
            return null;
        }
    }
    public class Transform : Component {
        public Transform parent;
        public bool IsChildOf(Transform root) {
            for(Transform p=this;p!=null;p=p.parent) if(p==root) return true;
            return false;
        }
    }
    public class GameObject : Object {
        readonly List<Component> components=new List<Component>();
        public Transform transform;
        public GameObject() { transform=Add<Transform>(); }
        public T Add<T>() where T:Component,new() { var c=new T();c.gameObject=this;components.Add(c);return c; }
        public T[] GetComponents<T>() where T:Component {
            var result=new List<T>();foreach(var c in components) if(c is T) result.Add((T)c);return result.ToArray();
        }
    }
    public class MonoBehaviour : Component { }
    public class Renderer : Component { }
    public class Animator : MonoBehaviour { }
}
namespace Spine.Unity { public class SkeletonRenderer : MonoBehaviour { } }
public class WorkerUnit : MonoBehaviour { public Spine.Unity.SkeletonRenderer spineRenderer; }
public class CreatureAnimScript : MonoBehaviour { }
public class CreatureUnit : MonoBehaviour { public CreatureAnimScript animTarget; }
public class ChildCreatureUnit : CreatureUnit { }
public class ProjectileUnit : MonoBehaviour { public GameObject animTarget; }
public class SwordProjectile : ProjectileUnit { }
public class SlimeGirlProjectile : MonoBehaviour { public Transform _effect; }
public class SlimeGirlWeaponProjectile : MonoBehaviour { public Transform _effect; }
public class MagicalGirlWeaponProjectile : MonoBehaviour { public Transform _effect; }
public class GeburahProjectile : MonoBehaviour { public Animator animator; }
namespace BinahBoss { public class BinahProjectile : MonoBehaviour { public Animator animator; } }

static class Fixture {
    static int checks;
    static readonly List<Renderer> renderers=new List<Renderer>();
    static GameObject Child(Transform parent) { var node=new GameObject();node.transform.parent=parent;return node; }
    static Spine.Unity.SkeletonRenderer Body(Transform parent) {
        var node=Child(parent);var skeleton=node.Add<Spine.Unity.SkeletonRenderer>();renderers.Add(node.Add<Renderer>());return skeleton;
    }
    static void Check(bool value,string label) { checks++; if(!value) throw new Exception(label); }
    static MotionTargets Read() { return new MotionTargets(renderers.ToArray()); }
    public static void Main() {
        var worker=new GameObject().Add<WorkerUnit>();worker.spineRenderer=Body(worker.transform);
        // Split body parts and duplicate render inputs must produce one visual track.
        renderers.Add(Child(worker.spineRenderer.transform).Add<Renderer>());
        renderers.Add(renderers[0]);
        Check(Read().Skeletons.Count==1,"worker/split deduplication");
        var creature=new GameObject().Add<CreatureUnit>();
        creature.animTarget=Child(creature.transform).Add<CreatureAnimScript>();
        var primary=Body(creature.animTarget.transform);var secondary=Body(creature.animTarget.transform);
        var index=Read();
        Check(index.Skeletons.Count==3,"creature multiple display branches");
        Check(index.Skeletons.ContainsKey(secondary.transform),"secondary branch tracked by its display transform");
        var child=new GameObject().Add<ChildCreatureUnit>();child.animTarget=Child(child.transform).Add<CreatureAnimScript>();
        Body(child.animTarget.transform);
        Check(Read().Skeletons.Count==4,"derived child creature");
        var sword=Child(creature.animTarget.transform).Add<SwordProjectile>();
        sword.animTarget=Child(sword.transform);var swordBody=Body(sword.animTarget.transform);
        index=Read();
        Check(index.Skeletons.Count==5,"nested derived projectile");
        Check(index.Owner(swordBody.gameObject.GetComponents<Renderer>()[0])==sword,"nearest projectile owns its own surface");
        Check(index.Skeletons.ContainsKey(swordBody.transform),"moving child, not stationary projectile controller");
        var slime=new GameObject().Add<SlimeGirlProjectile>();slime._effect=Child(slime.transform).transform;Body(slime._effect);
        var slimeWeapon=new GameObject().Add<SlimeGirlWeaponProjectile>();slimeWeapon._effect=Child(slimeWeapon.transform).transform;Body(slimeWeapon._effect);
        var magic=new GameObject().Add<MagicalGirlWeaponProjectile>();magic._effect=Child(magic.transform).transform;Body(magic._effect);
        var geburah=new GameObject().Add<GeburahProjectile>();geburah.animator=Child(geburah.transform).Add<Animator>();Body(geburah.animator.transform);
        var binah=new GameObject().Add<BinahBoss.BinahProjectile>();binah.animator=Child(binah.transform).Add<Animator>();Body(binah.animator.transform);
        Check(Read().Skeletons.Count==10,"five concrete display-root adapters");
        // Sibling UI/selection markers and arbitrary unknown objects are not bodies.
        Body(worker.transform);Body(new GameObject().transform);
        Check(Read().Skeletons.Count==10,"outside display root and unknown owner excluded");
        var unsupported=Child(creature.animTarget.transform).Add<Renderer>();renderers.Add(unsupported);
        Check(Read().UnsupportedRenderers==1,"unsupported sprite/effect withheld and diagnosed");
        var noVisual=new GameObject().Add<CreatureUnit>();Body(noVisual.transform);
        Check(Read().Skeletons.Count==10,"missing explicit visual root does not broaden selection");
        secondary.transform.parent=null;
        Check(Read().Skeletons.Count==9,"reparenting invalidates ownership on next capture");
        var fresh=new GameObject().Add<CreatureUnit>();fresh.animTarget=Child(fresh.transform).Add<CreatureAnimScript>();
        secondary.transform.parent=fresh.animTarget.transform;
        Check(Read().Skeletons.Count==10,"new owner discovered without stale cross-frame cache");
        Check(Read().Owner(primary.gameObject.GetComponents<Renderer>()[0])==creature,"original ownership intact");
        Console.WriteLine("PASS "+checks+" candidate adapter checks (hierarchy fixture, not rendering)");
    }
}
